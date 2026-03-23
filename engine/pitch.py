from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import logging
import math
import numpy as np
import cv2

log = logging.getLogger("pitch")


PITCH_ZONES = {
    "defensive_third": (0.0, 35.0),
    "middle_third": (35.0, 70.0),
    "attacking_third": (70.0, 105.0),
}


@dataclass
class PitchConfig:
    pitch_length_m: float = 105.0
    pitch_width_m: float = 68.0
    min_green_ratio: float = 0.12
    sample_every_n_frames: int = 10
    use_bottom_center: bool = True
    enabled: bool = True


class PitchCalibrator:
    """
    כיול מגרש baseline מקצועי ויציב:
    - מזהה אזור דשא
    - בונה מלבן מגרש מקורב
    - מחשב homography למגרש סטנדרטי (105x68)
    - ממיר נקודות פיקסל -> מטרים
    """

    def __init__(self, config: PitchConfig):
        self.config = config
        self.h_matrix: Optional[np.ndarray] = None
        self.last_src_quad: Optional[np.ndarray] = None
        self.last_dst_quad: Optional[np.ndarray] = None

    def _green_mask(self, frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower = np.array([30, 25, 25], dtype=np.uint8)
        upper = np.array([95, 255, 255], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower, upper)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask

    def _largest_contour_bbox(self, mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        h, w = mask.shape[:2]

        if area < h * w * self.config.min_green_ratio:
            return None

        x, y, bw, bh = cv2.boundingRect(c)
        return x, y, bw, bh

    def _white_mask(self, frame: np.ndarray, green_mask: np.ndarray) -> np.ndarray:
        """Return mask of white pixels that lie on or near the green pitch area."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white = cv2.inRange(hsv, np.array([0, 0, 170], dtype=np.uint8),
                                 np.array([180, 55, 255], dtype=np.uint8))
        dilated = cv2.dilate(green_mask, np.ones((20, 20), np.uint8), iterations=1)
        return cv2.bitwise_and(white, dilated)

    def _estimate_from_lines(self, frame: np.ndarray) -> bool:
        """
        Calibrate using white pitch line detection (Hough).

        Strategy for side-on cameras:
          1. Find near-horizontal white lines (touchlines).
          2. The two most vertically-separated ones define the pitch width (68 m).
          3. Their combined x-span defines the visible pitch length portion.

        Returns True and sets h_matrix when successful.
        """
        h, w = frame.shape[:2]
        green_mask = self._green_mask(frame)
        white = self._white_mask(frame, green_mask)

        if white.sum() // 255 < 300:
            return False

        edges = cv2.Canny(white, 50, 150, apertureSize=3)
        min_line_len = max(w // 10, 40)
        lines = cv2.HoughLinesP(
            edges, rho=1, theta=np.pi / 180,
            threshold=40, minLineLength=min_line_len, maxLineGap=25,
        )
        if lines is None or len(lines) < 2:
            return False

        # Keep only near-horizontal lines (|angle| < 20°)
        h_lines = []
        for seg in lines:
            x1, y1, x2, y2 = seg[0]
            dx = x2 - x1
            if dx == 0:
                continue
            angle = abs(math.degrees(math.atan2(abs(y2 - y1), abs(dx))))
            if angle < 20:
                h_lines.append((x1, y1, x2, y2))

        if len(h_lines) < 2:
            return False

        # Cluster lines by vertical position to find two distinct touchlines
        h_lines.sort(key=lambda l: (l[1] + l[3]) / 2)
        top_line  = h_lines[0]
        bot_line  = h_lines[-1]
        top_y = (top_line[1] + top_line[3]) / 2.0
        bot_y = (bot_line[1] + bot_line[3]) / 2.0

        # Require a meaningful vertical separation
        if bot_y - top_y < h * 0.12:
            return False

        # x-extent from all detected horizontal lines
        all_x = [l[0] for l in h_lines] + [l[2] for l in h_lines]
        left_x  = float(min(all_x))
        right_x = float(max(all_x))

        if right_x - left_x < w * 0.25:
            return False

        src = np.array([
            [left_x,  top_y],
            [right_x, top_y],
            [right_x, bot_y],
            [left_x,  bot_y],
        ], dtype=np.float32)

        dst = np.array([
            [0.0,                          0.0],
            [self.config.pitch_length_m,   0.0],
            [self.config.pitch_length_m,   self.config.pitch_width_m],
            [0.0,                          self.config.pitch_width_m],
        ], dtype=np.float32)

        h_matrix = cv2.getPerspectiveTransform(src, dst)
        if h_matrix is None:
            return False

        self.h_matrix      = h_matrix
        self.last_src_quad = src
        self.last_dst_quad = dst
        log.info("pitch calibrated via line detection  top_y=%.0f  bot_y=%.0f  x=[%.0f,%.0f]",
                 top_y, bot_y, left_x, right_x)
        return True

    def estimate_from_frame(self, frame: np.ndarray) -> bool:
        if frame is None or frame.size == 0:
            return False

        # Prefer line-based calibration; fall back to green bounding box.
        if self._estimate_from_lines(frame):
            return True

        h, w = frame.shape[:2]
        mask = self._green_mask(frame)
        bbox = self._largest_contour_bbox(mask)

        if bbox is None:
            src = np.array([
                [w * 0.05, h * 0.15],
                [w * 0.95, h * 0.15],
                [w * 0.95, h * 0.95],
                [w * 0.05, h * 0.95],
            ], dtype=np.float32)
        else:
            x, y, bw, bh = bbox
            src = np.array([
                [x + bw * 0.08, y + bh * 0.06],
                [x + bw * 0.92, y + bh * 0.06],
                [x + bw * 0.98, y + bh * 0.98],
                [x + bw * 0.02, y + bh * 0.98],
            ], dtype=np.float32)

        dst = np.array([
            [0.0,                        0.0],
            [self.config.pitch_length_m, 0.0],
            [self.config.pitch_length_m, self.config.pitch_width_m],
            [0.0,                        self.config.pitch_width_m],
        ], dtype=np.float32)

        h_matrix = cv2.getPerspectiveTransform(src, dst)
        if h_matrix is None:
            return False

        self.h_matrix      = h_matrix
        self.last_src_quad = src
        self.last_dst_quad = dst
        log.info("pitch calibrated via green bbox  src=%s", src.tolist())
        return True

    def is_ready(self) -> bool:
        return self.h_matrix is not None

    def calibrated_meters_per_pixel(self, frame_width: int, frame_height: int) -> float:
        """
        Derive the real pixel→metre scale from the homography at mid-pitch.
        Transforms two horizontally-adjacent pixels and measures their
        real-world separation.  Falls back to DEFAULT_METERS_PER_PIXEL when
        the homography is not available or produces an implausible result.
        """
        if self.h_matrix is None:
            return DEFAULT_METERS_PER_PIXEL
        cx, cy = frame_width / 2.0, frame_height / 2.0
        p0 = self.pixel_to_pitch(cx, cy)
        p1 = self.pixel_to_pitch(cx + 1.0, cy)
        if p0 is None or p1 is None:
            return DEFAULT_METERS_PER_PIXEL
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        mpp = math.sqrt(dx * dx + dy * dy)
        # Sanity: valid range for football-pitch cameras is roughly 0.01–0.5 m/px
        if 0.01 <= mpp <= 0.5:
            return mpp
        return DEFAULT_METERS_PER_PIXEL

    def pixel_to_pitch(self, x: float, y: float) -> Optional[Tuple[float, float]]:
        if self.h_matrix is None:
            return None

        pt = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.h_matrix)

        px = float(transformed[0, 0, 0])
        py = float(transformed[0, 0, 1])

        px = max(0.0, min(self.config.pitch_length_m, px))
        py = max(0.0, min(self.config.pitch_width_m, py))

        return px, py

    def bbox_anchor(self, bbox: List[float]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        if self.config.use_bottom_center:
            return (float((x1 + x2) / 2.0), float(y2))
        return (float((x1 + x2) / 2.0), float((y1 + y2) / 2.0))

    def export_meta(self) -> Dict:
        return {
            "ready": self.is_ready(),
            "pitch_length_m": self.config.pitch_length_m,
            "pitch_width_m": self.config.pitch_width_m,
            "src_quad": None if self.last_src_quad is None else self.last_src_quad.tolist(),
            "dst_quad": None if self.last_dst_quad is None else self.last_dst_quad.tolist(),
        }


# Fastest recorded human sprint ~10.4 m/s (Usain Bolt).
# 11 m/s (≈40 km/h) is the hard ceiling — anything above this is a tracking
# artifact (ID swap, bad homography jump) and is discarded entirely.
MAX_REALISTIC_SPEED_MPS = 11.5   # 41.4 km/h — Mbappé/Usain Bolt range; 10.0 was too aggressive, cut 3-5% of real sprints

# Youth players rarely exceed 18 km/h in a sprint.
SPRINT_THRESHOLD_MPS    = 5.0    # 18 km/h
SPRINT_MIN_DURATION_S   = 0.5    # sprint must be sustained ≥ 0.5 s to count


class PositionKalmanFilter:
    """2D constant-velocity Kalman filter for smoothing player pixel positions."""

    def __init__(self, process_noise: float = 1.0, measurement_noise: float = 5.0):
        # State: [x, y, vx, vy]
        self.F = np.eye(4, dtype=np.float64)
        self.F[0, 2] = 1.0
        self.F[1, 3] = 1.0
        self.H = np.zeros((2, 4), dtype=np.float64)
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0
        self.Q = np.eye(4, dtype=np.float64) * process_noise
        self.R = np.eye(2, dtype=np.float64) * measurement_noise
        self.P = np.eye(4, dtype=np.float64) * 500.0
        self.x: Optional[np.ndarray] = None

    def update(self, x: float, y: float) -> Tuple[float, float]:
        z = np.array([[x], [y]], dtype=np.float64)
        if self.x is None:
            self.x = np.array([[x], [y], [0.0], [0.0]], dtype=np.float64)
            return x, y
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q
        S = self.H @ P_pred @ self.H.T + self.R
        K = P_pred @ self.H.T @ np.linalg.inv(S)
        self.x = x_pred + K @ (z - self.H @ x_pred)
        self.P = (np.eye(4) - K @ self.H) @ P_pred
        return float(self.x[0, 0]), float(self.x[1, 0])

# Pixel-to-metre scale for angled / side-view cameras.
# Calibrated from debug frames: centre circle (~18.3 m diameter) spans
# ~170 px horizontally at mid-field → 18.3/170 ≈ 0.108 m/px.
# Using 0.09 (conservative) to account for perspective compression at angles.
# Tune this value if your camera distance / zoom differs.
DEFAULT_METERS_PER_PIXEL = 0.09


class WorldMetrics:
    """
    מחשב מרחקים ומהירויות בעולם אמיתי על בסיס נקודות מגרש.
    """

    @staticmethod
    def _step_distance(p0: Dict, p1: Dict, mpp: float) -> float:
        """Return real-world distance (metres) between two track points.

        Uses pitch-calibrated homography coordinates only when BOTH points
        were mapped via a real perspective transform (_homography=True).
        Falls back to pixel distance × mpp for uncalibrated/normalised coords.
        """
        if (p0.get("_homography") and p1.get("_homography")
                and "pitch_x" in p0 and "pitch_x" in p1):
            dx = p1["pitch_x"] - p0["pitch_x"]
            dy = p1["pitch_y"] - p0["pitch_y"]
        else:
            dx = (p1["x"] - p0["x"]) * mpp
            dy = (p1["y"] - p0["y"]) * mpp
        return float((dx * dx + dy * dy) ** 0.5)

    def compute_track_metrics(self, tracks: List[Dict], fps: float,
                              meters_per_pixel: float = DEFAULT_METERS_PER_PIXEL) -> Dict:
        if not tracks:
            return {
                "player_count": 0,
                "total_distance_m": 0.0,
                "max_speed_mps": 0.0,
                "sprint_count": 0,
            }

        by_track: Dict = {}
        for tr in tracks:
            by_track.setdefault(tr["track_id"], []).append(tr)

        total_distance = 0.0
        max_speed = 0.0
        sprint_count = 0  # distinct sustained-sprint events across all players

        for tid, points in by_track.items():
            points = sorted(points, key=lambda p: p["frame"])
            in_sprint = False
            sprint_duration = 0.0

            for i in range(1, len(points)):
                p0, p1 = points[i - 1], points[i]
                dist = self._step_distance(p0, p1, meters_per_pixel)

                dt_frames = max(1, p1["frame"] - p0["frame"])
                dt = dt_frames / max(fps, 1e-6)
                speed = dist / max(dt, 1e-6)

                if speed > MAX_REALISTIC_SPEED_MPS:
                    continue

                total_distance += dist
                max_speed = max(max_speed, speed)

                # Sustained-sprint detection (mirrors compute_per_player_metrics)
                if speed >= SPRINT_THRESHOLD_MPS:
                    if not in_sprint:
                        in_sprint = True
                        sprint_duration = 0.0
                    sprint_duration += dt
                else:
                    if in_sprint and sprint_duration >= SPRINT_MIN_DURATION_S:
                        sprint_count += 1
                    in_sprint = False
                    sprint_duration = 0.0

            if in_sprint and sprint_duration >= SPRINT_MIN_DURATION_S:
                sprint_count += 1

        return {
            "player_count": len(by_track),
            "total_distance_m": round(total_distance, 2),
            "total_distance_km": round(total_distance / 1000.0, 4),
            "max_speed_mps": round(max_speed, 2),
            "max_speed_kmh": round(max_speed * 3.6, 1),
            "sprint_count": int(sprint_count),
        }

    def compute_ball_proximity(
        self,
        target_points: List[Dict],
        ball_history: List[Dict],
        fps: float,
        frame_skip: int,
        meters_per_pixel: float = DEFAULT_METERS_PER_PIXEL,
        proximity_m: float = 1.0,
    ) -> Dict:
        """
        Count frames where the target player was within *proximity_m* metres
        of the ball.  Returns seconds, percentage of tracked time, and a
        formatted "M:SS" string.

        Uses homography pitch coordinates when available on both the player
        and the ball; falls back to pixel × mpp otherwise.
        """
        ball_by_frame: Dict[int, Dict] = {b["frame"]: b for b in ball_history}
        if not ball_by_frame or not target_points:
            return {"ball_time_s": 0.0, "ball_time_pct": 0.0, "ball_time_str": "0:00"}

        proximity_frames = 0
        for pt in target_points:
            ball = ball_by_frame.get(pt["frame"])
            if ball is None:
                continue

            if (pt.get("_homography") and "pitch_x" in pt and "pitch_x" in ball):
                dx = pt["pitch_x"] - ball["pitch_x"]
                dy = pt["pitch_y"] - ball["pitch_y"]
            else:
                dx = (pt["x"] - ball["x"]) * meters_per_pixel
                dy = (pt["y"] - ball["y"]) * meters_per_pixel

            if dx * dx + dy * dy <= proximity_m * proximity_m:
                proximity_frames += 1

        total_frames = max(len(target_points), 1)
        # Each decoded frame represents frame_skip real video frames
        prox_s = proximity_frames * frame_skip / max(fps, 1)
        total_s = total_frames * frame_skip / max(fps, 1)
        pct = (proximity_frames / total_frames) * 100

        mins = int(prox_s // 60)
        secs = int(prox_s % 60)
        return {
            "ball_time_s":   round(prox_s, 1),
            "ball_time_pct": round(pct, 1),
            "ball_time_str": f"{mins}:{secs:02d}",
        }

    def heatmap_pitch_points(self, tracks: List[Dict]) -> List[List[float]]:
        out = []
        for tr in tracks:
            if "pitch_x" in tr and "pitch_y" in tr:
                out.append([round(float(tr["pitch_x"]), 3), round(float(tr["pitch_y"]), 3)])
        return out

    def _zone_for_x(self, x: float) -> str:
        for zone_name, (lo, hi) in PITCH_ZONES.items():
            if lo <= x < hi:
                return zone_name
        return "attacking_third"

    @staticmethod
    def _rolling_median(values: List[float], window: int = 5) -> List[float]:
        """Apply a rolling median of *window* size to *values*."""
        if not values:
            return []
        half = window // 2
        out = []
        for i in range(len(values)):
            lo = max(0, i - half)
            hi = min(len(values), i + half + 1)
            out.append(float(np.median(values[lo:hi])))
        return out

    def compute_per_player_metrics(self, tracks: List[Dict], fps: float,
                                   meters_per_pixel: float = DEFAULT_METERS_PER_PIXEL,
                                   frame_skip: int = 1) -> List[Dict]:
        """
        Returns per-player stats: distance_m, avg_speed_mps, max_speed_mps,
        sprint_count, zone_frames.

        Improvements over the naive approach:
        - Kalman filter smooths noisy pixel positions before distance computation.
        - Rolling median over 5-frame windows reduces per-step speed noise.
        - Sprints only counted when sustained ≥ SPRINT_MIN_DURATION_S seconds.
        """
        if not tracks:
            return []

        by_track: Dict[int, List[Dict]] = {}
        for tr in tracks:
            by_track.setdefault(tr["track_id"], []).append(tr)

        results = []
        for tid, points in by_track.items():
            points = sorted(points, key=lambda p: p["frame"])

            # ── 1. Kalman-smooth pixel positions AND pitch coordinates ────────
            kf       = PositionKalmanFilter()
            kf_pitch = PositionKalmanFilter(process_noise=0.5, measurement_noise=1.5)
            smoothed: List[Dict] = []
            for pt in points:
                sx, sy = kf.update(pt["x"], pt["y"])
                sp = dict(pt)
                sp["x"] = sx
                sp["y"] = sy
                # Also smooth pitch coords so that _step_distance (homography path)
                # benefits from the same noise suppression.
                if sp.get("_homography") and "pitch_x" in sp and sp["pitch_x"] is not None:
                    spx, spy = kf_pitch.update(float(sp["pitch_x"]), float(sp["pitch_y"]))
                    sp["pitch_x"] = spx
                    sp["pitch_y"] = spy
                smoothed.append(sp)

            # ── 2. Per-step distances, raw speeds, and time deltas ───────────
            zone_frames: Dict[str, int] = {z: 0 for z in PITCH_ZONES}
            raw_dists: List[float] = []
            raw_speeds: List[float] = []
            raw_dts: List[float] = []

            for i, pt in enumerate(smoothed):
                if pt.get("pitch_x") is not None:
                    zone_frames[self._zone_for_x(pt["pitch_x"])] += 1
                if i == 0:
                    continue

                p0, p1 = smoothed[i - 1], smoothed[i]
                dist = self._step_distance(p0, p1, meters_per_pixel)
                dt_frames = max(1, p1["frame"] - p0["frame"])
                dt = dt_frames / max(fps, 1e-6)
                spd = dist / max(dt, 1e-6)

                if spd > MAX_REALISTIC_SPEED_MPS:
                    continue  # tracking artifact — discard step

                raw_dists.append(dist)
                raw_speeds.append(spd)
                raw_dts.append(dt)

            # ── 3. Rolling-median speed (3-frame window) ─────────────────────
            # With frame_skip=10 a 5-frame window covers 2 s — too wide, blurs sprints.
            # 3 frames = 1.2 s: responsive to genuine speed changes without noise.
            smoothed_speeds = self._rolling_median(raw_speeds, window=3)

            total_dist = sum(raw_dists)
            max_spd = max(smoothed_speeds) if smoothed_speeds else 0.0
            avg_spd = sum(smoothed_speeds) / len(smoothed_speeds) if smoothed_speeds else 0.0

            # ── 4. Sustained sprint detection (≥ SPRINT_MIN_DURATION_S) ──────
            sprint_count = 0
            in_sprint = False
            sprint_duration = 0.0
            for spd, dt in zip(smoothed_speeds, raw_dts):
                if spd >= SPRINT_THRESHOLD_MPS:
                    if not in_sprint:
                        in_sprint = True
                        sprint_duration = 0.0
                    sprint_duration += dt
                else:
                    if in_sprint and sprint_duration >= SPRINT_MIN_DURATION_S:
                        sprint_count += 1
                    in_sprint = False
                    sprint_duration = 0.0
            if in_sprint and sprint_duration >= SPRINT_MIN_DURATION_S:
                sprint_count += 1

            team_id = points[-1].get("team_id") if points else None
            results.append({
                "track_id": tid,
                "team_id": team_id,
                "distance_m": round(total_dist, 2),
                "distance_km": round(total_dist / 1000.0, 4),
                "avg_speed_mps": round(avg_spd, 3),
                "avg_speed_kmh": round(avg_spd * 3.6, 1),
                "max_speed_mps": round(max_spd, 3),
                "max_speed_kmh": round(max_spd * 3.6, 1),
                "sprint_count": sprint_count,
                "zone_frames": zone_frames,
                # Multiply by frame_skip so that total_frames / fps = real tracked seconds.
                "total_frames": len(points) * max(1, frame_skip),
            })

        results.sort(key=lambda p: p["distance_m"], reverse=True)
        return results
