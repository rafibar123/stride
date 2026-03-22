from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import cv2
import logging
import time
import numpy as np

from engine.detection import Detector, DetectionConfig
from engine.events import EventEngine, EventsConfig
from engine.team import TeamClassifier, TeamClassificationConfig
from engine.pitch import PitchCalibrator, PitchConfig, WorldMetrics, DEFAULT_METERS_PER_PIXEL
from engine.rating import compute_player_rating
from engine.passes import detect_passes
from engine.advanced_metrics import compute_advanced_metrics

log = logging.getLogger("pipeline")


@dataclass
class PipelineConfig:
    max_duration_s: float = 30.0  # hard cap on analysed video duration
    frame_skip: int = 10         # process every Nth frame; 1 = every frame, 10 = every 10th
    # Pixel-to-metre scale for angled cameras where homography is unavailable.
    # Default tuned for a 576 px-wide side-angle TikTok shot (~35 m visible).
    meters_per_pixel: float = DEFAULT_METERS_PER_PIXEL
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    events: EventsConfig = field(default_factory=EventsConfig)
    team: TeamClassificationConfig = field(default_factory=TeamClassificationConfig)
    pitch: PitchConfig = field(default_factory=PitchConfig)


class PipelineResult:
    def __init__(
        self,
        run_id: str,
        engine_name: str,
        frames_processed: int,
        fps: float,
        tracks: List[Dict],
        ball_track: List[Dict],
        heatmap_points: List[List[float]],
        motion_metrics: Dict,
        per_player_metrics: List[Dict],
        event_metrics: Dict,
        events: List[Dict],
        pass_network: List[Dict],
        team_pass_network: List[Dict],
        possession_by_team: List[Dict],
        possession_by_player: List[Dict],
        pitch_meta: Dict,
        modules_completed: List[str],
        modules_failed: List[str],
        errors: List[str],
        quality: Dict,
        video_meta: Dict,
        team_prototypes: Dict,
        rating: Dict,
        pass_stats: Dict,
        advanced_metrics: Dict,
    ):
        self.run_id = run_id
        self.engine_name = engine_name
        self.frames_processed = frames_processed
        self.fps = fps
        self.tracks = tracks
        self.ball_track = ball_track
        self.heatmap_points = heatmap_points
        self.motion_metrics = motion_metrics
        self.per_player_metrics = per_player_metrics
        self.event_metrics = event_metrics
        self.events = events
        self.pass_network = pass_network
        self.team_pass_network = team_pass_network
        self.possession_by_team = possession_by_team
        self.possession_by_player = possession_by_player
        self.pitch_meta = pitch_meta
        self.modules_completed = modules_completed
        self.modules_failed = modules_failed
        self.errors = errors
        self.quality = quality
        self.video_meta = video_meta
        self.team_prototypes = team_prototypes
        self.rating = rating
        self.pass_stats = pass_stats
        self.advanced_metrics = advanced_metrics

    def to_dict(self):
        return {
            "engine": self.engine_name,
            "status": "success",
            "run_id": self.run_id,
            "frames_processed": self.frames_processed,
            "fps": round(self.fps, 2),
            "tracks": self.tracks[:400],
            "ball_track": self.ball_track[:300],
            "heatmap_points": self.heatmap_points[:1500],
            "motion_metrics": self.motion_metrics,
            "per_player_metrics": self.per_player_metrics,
            "event_metrics": self.event_metrics,
            "events": self.events[:300],
            "pass_network": self.pass_network,
            "team_pass_network": self.team_pass_network,
            "possession_by_team": self.possession_by_team,
            "possession_by_player": self.possession_by_player,
            "pitch": self.pitch_meta,
            "modules_completed": self.modules_completed,
            "modules_failed": self.modules_failed,
            "errors": self.errors,
            "quality": self.quality,
            "video": self.video_meta,
            "team_prototypes": {
                str(k): v.tolist() for k, v in self.team_prototypes.items()
            },
            "rating": self.rating,
            "pass_stats": self.pass_stats,
            "advanced_metrics": self.advanced_metrics,
        }


def _jersey_color_score(frame, bbox: list, hex_color: str) -> float:
    """
    Return 0-1 similarity between the detection's torso crop and *hex_color*.
    1.0 = perfect match, 0.0 = opposite colour.
    """
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        target = np.array([b, g, r], dtype=np.float32)  # BGR

        x1, y1, x2, y2 = [int(v) for v in bbox]
        h = y2 - y1
        # Sample the middle-third (torso), avoid head and legs
        crop = frame[y1 + h // 4: y1 + (3 * h) // 4, x1:x2]
        if crop.size == 0:
            return 0.5

        mean_bgr = crop.reshape(-1, 3).mean(axis=0).astype(np.float32)
        dist = float(np.linalg.norm(mean_bgr - target))
        # max possible distance = sqrt(255^2 * 3) ≈ 441
        return max(0.0, 1.0 - dist / 441.0)
    except Exception:
        return 0.5


def run_pipeline(video_path: str, config: PipelineConfig, run_id: str, progress_cb=None,
                 click_x: Optional[float] = None, click_y: Optional[float] = None,
                 jersey_color: Optional[str] = None) -> PipelineResult:
    """
    progress_cb(pct: float, stage: str) is called at key milestones.
    pct is 0-100.  stage is a short machine-readable label.
    """
    def _report(pct: float, stage: str):
        log.info("[%s] %.0f%%  %s", run_id, pct, stage)
        if progress_cb:
            try:
                progress_cb(round(pct, 1), stage)
            except Exception:
                pass  # never let a broken callback kill the pipeline
    t0 = time.time()
    log.info("[%s] pipeline start  video=%s  max_duration=%.0fs  frame_skip=%d",
             run_id, video_path, config.max_duration_s, config.frame_skip)
    _report(0, "starting")

    modules_completed = []
    modules_failed = []
    errors = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log.error("[%s] opencv could not open video: %s", run_id, video_path)
        raise RuntimeError("opencv could not open video")

    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps and fps > 0 else 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    max_frames = int(fps * config.max_duration_s)
    log.info("[%s] video opened  %dx%d  %.1f fps  ~%d total frames  cap=%d frames (%.0fs)",
             run_id, width, height, fps, total_frames, max_frames, config.max_duration_s)
    _report(4, "video_opened")

    log.info("[%s] loading models…", run_id)
    _report(5, "models_loading")
    t_models = time.time()
    detector = Detector(config.detection)
    team_classifier = TeamClassifier(config.team)
    event_engine = EventEngine(config.events)
    pitch_calibrator = PitchCalibrator(config.pitch)
    world_metrics = WorldMetrics()
    log.info("[%s] models ready  %.2fs", run_id, time.time() - t_models)
    _report(10, "detecting")

    # frame_idx tracks the real video frame number so that all timestamp-based
    # calculations (speed, distance) remain accurate regardless of frame_skip.
    frame_idx = 0        # real video frame counter (wall-clock position)
    frames_decoded = 0   # how many frames we actually ran through the model
    heatmap_points = []
    frame_skip = max(1, config.frame_skip)

    team_votes = defaultdict(lambda: defaultdict(int))
    track_history: Dict[int, List[Dict]] = {}
    first_frame = None
    target_track_id: Optional[int] = None

    log.info("[%s] entering frame loop", run_id)
    t_loop = time.time()

    try:
        while True:
            # grab() advances the video position without decoding (fast).
            # We decode only every frame_skip-th frame via retrieve().
            ok = cap.grab()
            if not ok:
                log.info("[%s] grab() returned False at frame_idx=%d — end of stream",
                         run_id, frame_idx)
                break

            frame_idx += 1
            if frame_idx > max_frames:
                log.info("[%s] reached duration cap at frame %d (%.0fs), stopping",
                         run_id, frame_idx, config.max_duration_s)
                break

            # skip frames that fall between sample points
            if (frame_idx - 1) % frame_skip != 0:
                continue

            ok, frame = cap.retrieve()
            if not ok:
                log.warning("[%s] retrieve() failed at frame_idx=%d", run_id, frame_idx)
                continue

            frames_decoded += 1

            # Detailed log every 10 decoded frames
            if frames_decoded % 10 == 0:
                elapsed = time.time() - t_loop
                fps_proc = frames_decoded / max(elapsed, 1e-6)
                total_cap = min(max_frames, total_frames or max_frames)
                pct_done = frame_idx / max(max_frames, 1) * 100
                log.info("[%s] frame %d/%d (%.0f%%)  decoded=%d  %.2f frames/s  elapsed=%.1fs",
                         run_id, frame_idx, total_cap, pct_done,
                         frames_decoded, fps_proc, elapsed)

            # Report progress on every decoded frame for smooth frontend updates
            loop_pct = frame_idx / max(max_frames, 1)
            stage = "tracking" if loop_pct > 0.3 else "detecting"
            _report(10 + loop_pct * 78, stage)

            if first_frame is None:
                first_frame = frame.copy()
                if config.pitch.enabled:
                    pitch_calibrator.estimate_from_frame(first_frame)
                log.info("[%s] pitch calibration done  ready=%s", run_id, pitch_calibrator.is_ready())

            ball_det = detector.detect_ball(frame)

            active_tracks = detector.detect_and_track(frame, frame_idx)
            active_tracks = team_classifier.classify(frame, active_tracks)

            # Accumulate track history for post-processing
            for tr in active_tracks:
                track_history.setdefault(tr["track_id"], []).append(tr)

            # Lock onto the player nearest the click point (first frame with detections)
            if target_track_id is None and click_x is not None and click_y is not None and active_tracks:
                click_px = click_x * width
                click_py = click_y * height
                diag2 = max(width * width + height * height, 1)

                def _lock_score(tr):
                    dx = tr["center"][0] - click_px
                    dy = tr["center"][1] - click_py
                    dist_score = (dx * dx + dy * dy) / diag2  # 0-1, lower = closer
                    if jersey_color and len(jersey_color) == 7:
                        # 70% distance, 30% jersey colour match
                        color_score = 1.0 - _jersey_color_score(frame, tr["bbox"], jersey_color)
                        return dist_score * 0.70 + color_score * 0.30
                    return dist_score

                best = min(active_tracks, key=_lock_score)
                target_track_id = best["track_id"]
                log.info("[%s] locked target track_id=%d  click=(%.3f, %.3f)  jersey=%s",
                         run_id, target_track_id, click_x, click_y, jersey_color)

            # collect team votes and player heatmap
            for tr in active_tracks:
                if tr.get("team_id") is not None:
                    team_votes[tr["track_id"]][tr["team_id"]] += 1

                # heatmap: target player only (or all when no click given)
                if target_track_id is not None and tr["track_id"] != target_track_id:
                    continue

                # Use foot position (bottom-centre of bbox) for ground accuracy
                bx1, by1, bx2, by2 = tr["bbox"]
                foot_x = (bx1 + bx2) / 2.0
                foot_y = by2

                if pitch_calibrator.is_ready():
                    pitch_xy = pitch_calibrator.pixel_to_pitch(foot_x, foot_y)
                    if pitch_xy is not None:
                        tr["pitch_x"] = round(float(pitch_xy[0]), 3)
                        tr["pitch_y"] = round(float(pitch_xy[1]), 3)
                        heatmap_points.append([tr["pitch_x"], tr["pitch_y"]])
                    else:
                        # calibrated but this point is outside the mapped area
                        heatmap_points.append([
                            round(foot_x / max(width, 1) * 105.0, 3),
                            round(foot_y / max(height, 1) * 68.0, 3),
                        ])
                else:
                    # No homography — normalise pixel → pitch coordinate space.
                    # Horizontal pixel axis ≈ pitch length (camera faces pitch side-on).
                    heatmap_points.append([
                        round(foot_x / max(width, 1) * 105.0, 3),
                        round(foot_y / max(height, 1) * 68.0, 3),
                    ])

            # Ball — update event engine only; ball is NOT part of player heatmap
            if ball_det is not None:
                if pitch_calibrator.is_ready():
                    ball_center = tuple(ball_det["center"])
                    pitch_xy = pitch_calibrator.pixel_to_pitch(ball_center[0], ball_center[1])
                    if pitch_xy is not None:
                        ball_det["pitch_x"] = round(float(pitch_xy[0]), 3)
                        ball_det["pitch_y"] = round(float(pitch_xy[1]), 3)

            event_engine.update(
                frame_idx=frame_idx,
                ball=ball_det,
                active_tracks=active_tracks,
                frame_width=width,
                frame_height=height
            )

        modules_completed.extend([
            "video_decode",
            "detection",
            "tracking",
            "team_classification",
            "pitch_calibration",
            "events"
        ])
        log.info("[%s] frame loop done  frames_scanned=%d  frames_decoded=%d  elapsed=%.2fs",
                 run_id, frame_idx, frames_decoded, time.time() - t_loop)

    except Exception as e:
        log.exception("[%s] exception in frame loop: %s", run_id, e)
        errors.append(str(e))
        modules_failed.append("runtime")

    cap.release()
    log.info("[%s] post-processing metrics…", run_id)
    _report(90, "post_processing")

    # Flatten track_history into the same format as the old tracker.export_tracks()
    tracks = []
    for tid, pts in track_history.items():
        for pt in pts:
            tracks.append({
                "frame": pt["frame"],
                "x": pt["center"][0],
                "y": pt["center"][1],
                "track_id": tid,
            })

    # attach stable team labels + stable pitch coords to exported tracks
    for tr in tracks:
        tid = tr["track_id"]

        if tid in team_votes and len(team_votes[tid]) > 0:
            best_team = max(team_votes[tid].items(), key=lambda kv: kv[1])[0]
            tr["team_id"] = best_team
            tr["team_label"] = f"team_{best_team}"
        else:
            tr["team_id"] = None
            tr["team_label"] = "unknown"

        if pitch_calibrator.is_ready():
            pitch_xy = pitch_calibrator.pixel_to_pitch(tr["x"], tr["y"])
            if pitch_xy is not None:
                tr["pitch_x"]     = round(float(pitch_xy[0]), 3)
                tr["pitch_y"]     = round(float(pitch_xy[1]), 3)
                tr["_homography"] = True
            else:
                # Point is outside the mapped area — normalised coords for zones only
                tr["pitch_x"]     = round(tr["x"] / max(width, 1) * 105.0, 3)
                tr["pitch_y"]     = round(tr["y"] / max(height, 1) * 68.0, 3)
                tr["_homography"] = False
        else:
            # No calibration — normalised pixel coords for zone tracking only.
            # _homography=False tells WorldMetrics to use meters_per_pixel instead.
            tr["pitch_x"]     = round(tr["x"] / max(width, 1) * 105.0, 3)
            tr["pitch_y"]     = round(tr["y"] / max(height, 1) * 68.0, 3)
            tr["_homography"] = False

    # Use homography-derived mpp when calibration succeeded, else fall back to config default
    if pitch_calibrator.is_ready():
        mpp = pitch_calibrator.calibrated_meters_per_pixel(width, height)
        log.info("[%s] calibrated mpp=%.4f m/px", run_id, mpp)
    else:
        mpp = config.meters_per_pixel
        log.info("[%s] fallback mpp=%.4f m/px (no calibration)", run_id, mpp)

    motion_metrics = world_metrics.compute_track_metrics(tracks, fps, mpp)
    per_player_metrics = world_metrics.compute_per_player_metrics(tracks, fps, mpp)
    # Filter to only the selected player when a click target was provided
    if target_track_id is not None:
        per_player_metrics = [p for p in per_player_metrics if p["track_id"] == target_track_id]
    modules_completed.append("per_player_metrics")
    event_metrics = event_engine.export_event_metrics()
    events = event_engine.export_events()
    ball_track = event_engine.export_ball_track()
    pass_network = event_engine.export_pass_network()
    team_pass_network = event_engine.export_team_pass_network()
    possession_by_team = event_engine.export_possession_by_team()
    possession_by_player = event_engine.export_possession_by_player()

    # ── Ball proximity ("time with ball") ──────────────────────────────────────
    if target_track_id is not None and per_player_metrics:
        try:
            target_points = [t for t in tracks if t["track_id"] == target_track_id]
            ball_prox = world_metrics.compute_ball_proximity(
                target_points=target_points,
                ball_history=ball_track,
                fps=fps,
                frame_skip=config.frame_skip,
                meters_per_pixel=mpp,
            )
            per_player_metrics[0].update(ball_prox)
            log.info("[%s] ball proximity  %.1fs  %.1f%%", run_id,
                     ball_prox["ball_time_s"], ball_prox["ball_time_pct"])
        except Exception as exc:
            log.warning("[%s] ball proximity failed: %s", run_id, exc)

    # ── Pass detection ─────────────────────────────────────────────────────────
    pass_stats: Dict = {}
    if target_track_id is not None and ball_track:
        try:
            pass_stats = detect_passes(
                ball_track=ball_track,
                target_track_id=target_track_id,
                track_history=track_history,
                fps=fps,
                frame_size=(width, height),
            )
            log.info(
                "[%s] pass detection done  total=%d  accurate=%d  accuracy=%.0f%%",
                run_id,
                pass_stats.get("total", 0),
                pass_stats.get("accurate", 0),
                pass_stats.get("accuracy_pct", 0),
            )
        except Exception as e:
            log.warning("[%s] pass detection failed: %s", run_id, e)
            pass_stats = {}

    # Overwrite EventEngine pass counters with the more accurate detect_passes() result
    if pass_stats:
        event_metrics["pass_success"] = int(pass_stats.get("accurate", event_metrics["pass_success"]))
        event_metrics["pass_fail"]    = int(pass_stats.get("failed",   event_metrics["pass_fail"]))

    # ── FIFA-style player rating ───────────────────────────────────────────────
    rating: Dict = {}
    if per_player_metrics:
        rating = compute_player_rating(
            per_player_metrics[0],
            fps,
            heatmap_points=heatmap_points,
            video_meta={"width": width, "height": height},
            pass_stats=pass_stats,
        )
        log.info("[%s] rating computed  overall=%.1f  phys=%.1f  att=%.1f  pos=%.1f  press=%.1f  pass=%.1f",
                 run_id, rating.get("overall", 0), rating.get("physical", 0),
                 rating.get("attacking", 0), rating.get("positioning", 0),
                 rating.get("pressing", 0), rating.get("passing", 0))

    # ── Advanced per-player metrics ────────────────────────────────────────────
    advanced_metrics: Dict = {}
    if target_track_id is not None:
        try:
            advanced_metrics = compute_advanced_metrics(
                track_history=track_history,
                target_track_id=target_track_id,
                fps=fps,
                meters_per_pixel=mpp,
            )
            log.info(
                "[%s] advanced metrics  activity=%s  dir_changes=%d  sprints=%d",
                run_id,
                advanced_metrics.get("activity", {}),
                advanced_metrics.get("direction_changes", 0),
                len(advanced_metrics.get("sprint_moments", [])),
            )
        except Exception as exc:
            log.warning("[%s] advanced metrics failed: %s", run_id, exc)

    modules_completed.append("world_metrics")
    log.info("[%s] pipeline complete  total=%.2fs  tracks=%d  events=%d  errors=%d",
             run_id, time.time() - t0, len(tracks), len(events), len(errors))
    _report(100, "done")

    quality = {
        "has_tracks": len(tracks) > 0,
        "has_ball_track": len(ball_track) > 0,
        "usable": frame_idx > 0 and len(tracks) > 0,
        "has_events": len(events) > 0,
        "has_pass_network": len(pass_network) > 0,
        "has_team_pass_network": len(team_pass_network) > 0,
        "has_team_possession": len(possession_by_team) > 0,
        "has_pitch_calibration": pitch_calibrator.is_ready(),
    }

    video_meta = {
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "frames_processed": frame_idx,
        "frames_decoded": frames_decoded,
        "frame_skip": frame_skip,
    }

    return PipelineResult(
        run_id=run_id,
        engine_name="vision-v8",
        frames_processed=frame_idx,
        fps=fps,
        tracks=tracks,
        ball_track=ball_track,
        heatmap_points=heatmap_points,
        motion_metrics=motion_metrics,
        per_player_metrics=per_player_metrics,
        event_metrics=event_metrics,
        events=events,
        pass_network=pass_network,
        team_pass_network=team_pass_network,
        possession_by_team=possession_by_team,
        possession_by_player=possession_by_player,
        pitch_meta=pitch_calibrator.export_meta(),
        modules_completed=modules_completed,
        modules_failed=modules_failed,
        errors=errors,
        quality=quality,
        video_meta=video_meta,
        team_prototypes={k: np.array(v) for k, v in team_classifier.prototypes.items()},
        rating=rating,
        pass_stats=pass_stats,
        advanced_metrics=advanced_metrics,
    )
