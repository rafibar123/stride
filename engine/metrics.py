import math
from typing import Dict, List


class MotionMetrics:
    """
    Legacy pixel-space motion metrics (used as fallback when pitch calibration is unavailable).
    Converts pixel distances to metres using a simple scale factor.
    """

    def __init__(self, pitch_width_m: float = 105.0, frame_width_px: int = 1920):
        self.scale = pitch_width_m / frame_width_px

    def _distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        dx = x2 - x1
        dy = y2 - y1
        return math.sqrt(dx * dx + dy * dy)

    def compute(self, tracks: List[Dict], fps: float) -> Dict:
        if not tracks:
            return {
                "player_count": 0,
                "total_distance_m": 0.0,
                "max_speed_mps": 0.0,
                "sprint_count": 0,
            }

        total_distance_px = 0.0
        max_speed = 0.0
        sprint_count = 0
        last = None

        for t in tracks:
            if last is None:
                last = t
                continue

            if t["frame"] == last["frame"]:
                continue

            d = self._distance(last["x"], last["y"], t["x"], t["y"])
            total_distance_px += d

            speed = (d * self.scale) * fps
            if speed > max_speed:
                max_speed = speed
            if speed > 7.0:
                sprint_count += 1

            last = t

        total_distance_m = total_distance_px * self.scale
        return {
            "player_count": len(tracks),
            "total_distance_m": round(total_distance_m, 2),
            "max_speed_mps": round(max_speed, 2),
            "sprint_count": sprint_count,
        }
