from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging
import math

log = logging.getLogger("events")


@dataclass
class EventsConfig:
    possession_radius_px: float = 90.0
    min_frames_for_possession: int = 2
    loss_grace_frames: int = 8
    min_pass_frames_gap: int = 4
    min_ball_move_for_shot_px: float = 14.0
    shot_cooldown_frames: int = 10


def euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


class EventEngine:
    """
    מנוע אירועים:
    - ownership smoothing
    - possession by player/team
    - touches
    - passes
    - turnovers
    - pass network
    - heuristic xT
    - heuristic xG
    """

    def __init__(self, config: EventsConfig):
        self.config = config

        self.ball_history: List[Dict] = []
        self.events: List[Dict] = []

        self.candidate_owner: Optional[int] = None
        self.candidate_team: Optional[int] = None
        self.owner_streak: int = 0

        self.confirmed_owner: Optional[int] = None
        self.confirmed_team: Optional[int] = None

        self.frames_since_owner_seen: int = 0
        self.last_touch_frame: Optional[int] = None
        self.last_shot_frame: Optional[int] = None

        self.touch_count = 0
        self.pass_success = 0
        self.pass_fail = 0
        self.turnover_count = 0
        self.shot_count = 0

        # ── Goal / assist tracking ────────────────────────────────────────────
        self.goal_count = 0
        self.assist_count = 0
        self.goal_events: List[Dict] = []

        # Shot pending confirmation: set in _maybe_register_shot, consumed by _maybe_confirm_goal
        self._pending_shot: Optional[Dict] = None

        # last_passer_to[player_id] = (passer_id, frame_idx) — used for assist detection
        self._last_passer_to: Dict[int, Tuple[int, int]] = {}

        self.possession_frames_by_player = defaultdict(int)
        self.possession_frames_by_team = defaultdict(int)
        self.pass_network = defaultdict(int)
        self.team_pass_network = defaultdict(int)

        self.team_touch_xs = defaultdict(list)
        self.xt_by_team = defaultdict(float)
        self.xg_by_team = defaultdict(float)

        self.last_threat_by_team = defaultdict(float)

    def _nearest_player(
        self,
        ball_center: Optional[Tuple[float, float]],
        active_tracks: List[Dict],
        possession_radius_px: float,
    ) -> Optional[Dict]:
        if ball_center is None:
            return None

        best = None
        best_dist = 1e9

        for tr in active_tracks:
            center = tuple(tr["center"])
            d = euclidean(ball_center, center)
            if d < best_dist:
                best = tr
                best_dist = d

        if best is None or best_dist > possession_radius_px:
            return None

        return {
            "track_id": best["track_id"],
            "team_id": best.get("team_id"),
            "distance": round(best_dist, 2)
        }

    def _infer_team_direction(self, team_id: Optional[int], frame_width: int) -> int:
        """
        +1 = תוקפת ימינה
        -1 = תוקפת שמאלה
        """
        if team_id is None:
            return 1

        xs1 = self.team_touch_xs.get(1, [])
        xs2 = self.team_touch_xs.get(2, [])

        if len(xs1) < 3 or len(xs2) < 3:
            return 1 if team_id == 1 else -1

        mean1 = sum(xs1) / len(xs1)
        mean2 = sum(xs2) / len(xs2)

        if mean1 < mean2:
            return 1 if team_id == 1 else -1
        return -1 if team_id == 1 else 1

    def _threat_score(self, x: float, y: float, width: int, height: int, direction: int) -> float:
        if width <= 0 or height <= 0:
            return 0.0

        nx = x / width
        ny = y / height

        if direction == -1:
            nx = 1.0 - nx

        centrality = max(0.0, 1.0 - abs(ny - 0.5) * 2.0)
        score = (0.72 * nx) + (0.28 * nx * centrality)
        return float(max(0.0, min(1.0, score)))

    def _estimate_xg(self, x: float, y: float, width: int, height: int, direction: int) -> float:
        if width <= 0 or height <= 0:
            return 0.0

        goal_x = width if direction == 1 else 0.0
        goal_y = height / 2.0

        dx = abs(goal_x - x)
        dy = abs(goal_y - y)

        distance = math.sqrt(dx * dx + dy * dy)
        norm_distance = distance / max(width, 1)

        # heuristic baseline
        xg = 0.55 * max(0.0, 1.0 - norm_distance * 1.6)

        # central shots worth more
        center_bonus = max(0.0, 1.0 - (abs(y - goal_y) / max(height / 2.0, 1)))
        xg += 0.25 * center_bonus

        return float(max(0.01, min(0.9, xg)))

    def _maybe_register_shot(
        self,
        frame_idx: int,
        ball_center: Tuple[float, float],
        owner_team: Optional[int],
        frame_width: int,
        frame_height: int
    ):
        if owner_team is None:
            return

        if self.last_shot_frame is not None and (frame_idx - self.last_shot_frame) < self.config.shot_cooldown_frames:
            return

        if len(self.ball_history) < 2:
            return

        prev = self.ball_history[-2]
        cur = self.ball_history[-1]

        # Normalise to frame width so threshold is resolution-independent.
        # ~2.2% of frame width ≈ 14 px at 640 px, 42 px at 1920 px.
        min_move = frame_width * 0.022
        move = euclidean((prev["x"], prev["y"]), (cur["x"], cur["y"]))
        if move < min_move:
            return

        direction = self._infer_team_direction(owner_team, frame_width)
        threat = self._threat_score(ball_center[0], ball_center[1], frame_width, frame_height, direction)

        # shot heuristic: threat zone high enough
        if threat < 0.78:
            return

        xg = self._estimate_xg(ball_center[0], ball_center[1], frame_width, frame_height, direction)
        self.xg_by_team[owner_team] += xg
        self.shot_count += 1
        self.last_shot_frame = frame_idx

        self.events.append({
            "frame": frame_idx,
            "type": "shot",
            "team_id": owner_team,
            "xg": round(xg, 4)
        })

        # Store as pending — next ball detections in goal zone will confirm a goal
        assist_candidate = self._last_passer_to.get(self.confirmed_owner or -1)
        self._pending_shot = {
            "frame":           frame_idx,
            "team_id":         owner_team,
            "direction":       direction,
            "scorer_id":       self.confirmed_owner,
            "assist_candidate": assist_candidate,   # (player_id, frame) or None
            "check_until":     frame_idx + self._SHOT_WINDOW_FRAMES,
        }

    # ── Goal-line crossing detection ──────────────────────────────────────────

    # FIFA goal dimensions (pitch coords): 7.32 m wide, centred on y=34 m
    _GOAL_Y_LO  = (68.0 - 7.32) / 2          # 30.34 m
    _GOAL_Y_HI  = (68.0 + 7.32) / 2          # 37.66 m
    _GOAL_MARGIN = 1.5                         # ±1.5 m tolerance for imprecise homography
    _GOAL_X_MARGIN = 1.0                       # how far past the line the ball must be
    _SHOT_WINDOW_FRAMES = 90                   # real-frame window after shot to check (~3.6 s at 25 fps)
    _ASSIST_MAX_FRAMES  = 200                  # max frames before shot for assist to count (~8 s)
    _PIXEL_GOAL_Y_FRAC  = 0.14                 # ±14% of frame height = goal post band
    _PIXEL_GOAL_X_FRAC  = 0.05                 # ball must be within 5% of frame edge

    def _maybe_confirm_goal(self, frame_idx: int, frame_width: int, frame_height: int) -> None:
        """Called each frame while a shot is pending. Confirms goal or expires the check."""
        if self._pending_shot is None:
            return

        # Expire window
        if frame_idx > self._pending_shot["check_until"]:
            self._pending_shot = None
            return

        # Need at least one ball reading after the shot
        if not self.ball_history:
            return
        last_ball = self.ball_history[-1]
        if last_ball["frame"] <= self._pending_shot["frame"]:
            return

        direction = self._pending_shot["direction"]
        goal_scored = False

        # ── Pitch-coordinate path (preferred — accurate to ~1 m) ─────────────
        if "pitch_x" in last_ball and "pitch_y" in last_ball:
            px = float(last_ball["pitch_x"])
            py = float(last_ball["pitch_y"])
            in_y = (self._GOAL_Y_LO - self._GOAL_MARGIN) <= py <= (self._GOAL_Y_HI + self._GOAL_MARGIN)
            if direction == 1 and px >= (105.0 - self._GOAL_X_MARGIN) and in_y:
                goal_scored = True
            elif direction == -1 and px <= self._GOAL_X_MARGIN and in_y:
                goal_scored = True
        else:
            # ── Pixel heuristic path ──────────────────────────────────────────
            bx = float(last_ball["x"])
            by = float(last_ball["y"])
            in_goal_y = abs(by - frame_height * 0.5) < frame_height * self._PIXEL_GOAL_Y_FRAC
            if direction == 1 and bx > frame_width * (1.0 - self._PIXEL_GOAL_X_FRAC) and in_goal_y:
                goal_scored = True
            elif direction == -1 and bx < frame_width * self._PIXEL_GOAL_X_FRAC and in_goal_y:
                goal_scored = True

        if not goal_scored:
            return

        # ── Goal confirmed ────────────────────────────────────────────────────
        self.goal_count += 1
        shot       = self._pending_shot
        scorer_id  = shot["scorer_id"]
        assist_id: Optional[int] = None

        entry = shot.get("assist_candidate")   # (player_id, frame_idx) or None
        if entry is not None:
            a_id, a_frame = entry
            if shot["frame"] - a_frame <= self._ASSIST_MAX_FRAMES:
                assist_id = a_id
                self.assist_count += 1

        ev = {
            "frame":     frame_idx,
            "type":      "goal",
            "team_id":   shot["team_id"],
            "scorer_id": scorer_id,
            "assist_id": assist_id,
        }
        self.goal_events.append(ev)
        self.events.append(ev)
        log.info("goal confirmed  frame=%d  scorer=%s  assist=%s", frame_idx, scorer_id, assist_id)
        self._pending_shot = None

    def update(self, frame_idx: int, ball: Optional[Dict], active_tracks: List[Dict], frame_width: int, frame_height: int):
        ball_center = None

        if ball is not None:
            ball_center = tuple(ball["center"])
            entry: Dict = {
                "frame": frame_idx,
                "x": round(ball_center[0], 2),
                "y": round(ball_center[1], 2),
                "conf": round(float(ball["conf"]), 4),
            }
            if "pitch_x" in ball:
                entry["pitch_x"] = ball["pitch_x"]
                entry["pitch_y"] = ball["pitch_y"]
            self.ball_history.append(entry)

        # Check if a pending shot has resulted in a goal (runs every frame ball detected)
        self._maybe_confirm_goal(frame_idx, frame_width, frame_height)

        # Normalise possession radius to frame width: 3% ≈ 3–5 metres on-pitch.
        # 14% (old value) was ~24m — way too generous, caused massive false possessions.
        possession_radius = frame_width * 0.03
        nearest = self._nearest_player(ball_center, active_tracks, possession_radius)

        if nearest is None:
            self.frames_since_owner_seen += 1
            if self.frames_since_owner_seen > self.config.loss_grace_frames:
                # Ball left possession — check if it looks like a shot in flight
                # (fast-moving ball in the final third, no player nearby)
                if ball_center is not None and self.confirmed_team is not None:
                    self._maybe_register_shot(
                        frame_idx=frame_idx,
                        ball_center=ball_center,
                        owner_team=self.confirmed_team,
                        frame_width=frame_width,
                        frame_height=frame_height,
                    )
                self.candidate_owner = None
                self.candidate_team = None
                self.owner_streak = 0
            return

        self.frames_since_owner_seen = 0

        cand_owner = nearest["track_id"]
        cand_team = nearest.get("team_id")

        if self.candidate_owner == cand_owner:
            self.owner_streak += 1
        else:
            self.candidate_owner = cand_owner
            self.candidate_team = cand_team
            self.owner_streak = 1

        if self.owner_streak < self.config.min_frames_for_possession:
            return

        owner_changed = (self.confirmed_owner != self.candidate_owner)
        prev_owner = self.confirmed_owner
        prev_team = self.confirmed_team

        self.confirmed_owner = self.candidate_owner
        self.confirmed_team = self.candidate_team

        self.possession_frames_by_player[self.confirmed_owner] += 1
        if self.confirmed_team is not None:
            self.possession_frames_by_team[self.confirmed_team] += 1

        if ball_center is not None and self.confirmed_team is not None:
            self.team_touch_xs[self.confirmed_team].append(ball_center[0])

            direction = self._infer_team_direction(self.confirmed_team, frame_width)
            threat = self._threat_score(ball_center[0], ball_center[1], frame_width, frame_height, direction)
            delta = max(0.0, threat - self.last_threat_by_team[self.confirmed_team])
            self.xt_by_team[self.confirmed_team] += delta
            self.last_threat_by_team[self.confirmed_team] = threat

            self._maybe_register_shot(
                frame_idx=frame_idx,
                ball_center=ball_center,
                owner_team=self.confirmed_team,
                frame_width=frame_width,
                frame_height=frame_height
            )

        if not owner_changed:
            return

        self.touch_count += 1
        self.events.append({
            "frame": frame_idx,
            "type": "touch",
            "player_id": self.confirmed_owner,
            "team_id": self.confirmed_team
        })

        if prev_owner is None:
            self.last_touch_frame = frame_idx
            return

        if self.last_touch_frame is not None and (frame_idx - self.last_touch_frame) >= self.config.min_pass_frames_gap:
            same_team = (
                prev_team is not None
                and self.confirmed_team is not None
                and prev_team == self.confirmed_team
            )

            if same_team:
                # Ball moved to a teammate → successful pass
                self.pass_success += 1
                self.pass_network[(prev_owner, self.confirmed_owner)] += 1
                if prev_team is not None and self.confirmed_team is not None:
                    self.team_pass_network[(prev_team, self.confirmed_team)] += 1

                # Track last passer to each player — used by goal assist detection
                self._last_passer_to[self.confirmed_owner] = (prev_owner, frame_idx)

                self.events.append({
                    "frame": frame_idx,
                    "type": "pass",
                    "from_player_id": prev_owner,
                    "to_player_id": self.confirmed_owner,
                    "from_team_id": prev_team,
                    "to_team_id": self.confirmed_team,
                    "accurate": True,
                })
            else:
                # Ball moved to an opponent → failed pass / turnover
                self.pass_fail += 1
                self.turnover_count += 1
                self.events.append({
                    "frame": frame_idx,
                    "type": "pass",
                    "from_player_id": prev_owner,
                    "to_player_id": self.confirmed_owner,
                    "from_team_id": prev_team,
                    "to_team_id": self.confirmed_team,
                    "accurate": False,
                })
                self.events.append({
                    "frame": frame_idx,
                    "type": "turnover",
                    "from_team_id": prev_team,
                    "to_team_id": self.confirmed_team,
                    "from_player_id": prev_owner,
                    "to_player_id": self.confirmed_owner,
                })

        self.last_touch_frame = frame_idx

    def export_goal_events(self) -> List[Dict]:
        return list(self.goal_events)

    def export_event_metrics(self) -> Dict:
        total_team_possession = sum(self.possession_frames_by_team.values())

        total_passes = self.pass_success + self.pass_fail
        pass_accuracy = round(self.pass_success / total_passes * 100, 1) if total_passes > 0 else 0.0

        return {
            "pass_success":   int(self.pass_success),
            "pass_fail":      int(self.pass_fail),
            "pass_total":     total_passes,
            "pass_accuracy":  pass_accuracy,
            "touch_count":    int(self.touch_count),
            "turnover_count": int(self.turnover_count),
            "shot_count":    int(self.shot_count),
            "goal_count":    int(self.goal_count),
            "assist_count":  int(self.assist_count),
            "event_count":   len(self.events),
            "xT_team_1": round(float(self.xt_by_team.get(1, 0.0)), 4),
            "xT_team_2": round(float(self.xt_by_team.get(2, 0.0)), 4),
            "xG_team_1": round(float(self.xg_by_team.get(1, 0.0)), 4),
            "xG_team_2": round(float(self.xg_by_team.get(2, 0.0)), 4),
            "team_1_possession_frames": int(self.possession_frames_by_team.get(1, 0)),
            "team_2_possession_frames": int(self.possession_frames_by_team.get(2, 0)),
            "total_possession_frames": int(total_team_possession),
        }

    def export_events(self) -> List[Dict]:
        return self.events

    def export_ball_track(self) -> List[Dict]:
        return self.ball_history

    def export_pass_network(self) -> List[Dict]:
        out = []
        for (src, dst), count in self.pass_network.items():
            out.append({
                "from_player_id": src,
                "to_player_id": dst,
                "count": int(count)
            })
        return out

    def export_team_pass_network(self) -> List[Dict]:
        out = []
        for (src, dst), count in self.team_pass_network.items():
            out.append({
                "from_team_id": src,
                "to_team_id": dst,
                "count": int(count)
            })
        return out

    def export_possession_by_team(self) -> List[Dict]:
        total = sum(self.possession_frames_by_team.values())
        out = []

        for team_id, frames in self.possession_frames_by_team.items():
            share = 0.0 if total == 0 else frames / total
            out.append({
                "team_id": team_id,
                "frames": int(frames),
                "share": round(share, 4)
            })

        out.sort(key=lambda x: x["frames"], reverse=True)
        return out

    def export_possession_by_player(self) -> List[Dict]:
        total = sum(self.possession_frames_by_player.values())
        out = []

        for player_id, frames in self.possession_frames_by_player.items():
            share = 0.0 if total == 0 else frames / total
            out.append({
                "player_id": player_id,
                "frames": int(frames),
                "share": round(share, 4)
            })

        out.sort(key=lambda x: x["frames"], reverse=True)
        return out
