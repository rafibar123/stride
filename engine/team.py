from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import cv2


@dataclass
class TeamClassificationConfig:
    min_crop_width: int = 12
    min_crop_height: int = 20
    min_saturation: int = 45
    min_value: int = 45
    second_team_distance_threshold: float = 40.0
    prototype_momentum: float = 0.15


class TeamClassifier:
    """
    סיווג קבוצות לפי צבע חולצה, בלי תלות חיצונית.
    שומר 2 פרוטוטייפים של צבע חולצה ומסווג שחקנים אליהם.
    """

    def __init__(self, config: TeamClassificationConfig):
        self.config = config
        self.prototypes: Dict[int, np.ndarray] = {}

    def _safe_crop(self, frame, bbox) -> Optional[np.ndarray]:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        return crop

    def _extract_jersey_feature(self, frame, bbox) -> Optional[np.ndarray]:
        crop = self._safe_crop(frame, bbox)
        if crop is None:
            return None

        h, w = crop.shape[:2]
        if w < self.config.min_crop_width or h < self.config.min_crop_height:
            return None

        # upper torso region
        y1 = int(h * 0.15)
        y2 = int(h * 0.55)
        x1 = int(w * 0.2)
        x2 = int(w * 0.8)

        torso = crop[y1:y2, x1:x2]
        if torso.size == 0:
            return None

        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)

        # מסכה שמפחיתה דשא/רקע כהה
        sat_mask = hsv[:, :, 1] >= self.config.min_saturation
        val_mask = hsv[:, :, 2] >= self.config.min_value

        # מסנן ירוק טיפוסי של דשא
        hue = hsv[:, :, 0]
        green_mask = (hue >= 35) & (hue <= 95)

        mask = sat_mask & val_mask & (~green_mask)

        pixels = torso[mask]
        if pixels is None or len(pixels) < 20:
            pixels = torso.reshape(-1, 3)

        if pixels is None or len(pixels) == 0:
            return None

        mean_bgr = pixels.mean(axis=0).astype(np.float32)
        return mean_bgr

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.linalg.norm(a - b))

    def _assign_team_id(self, feat: np.ndarray) -> int:
        if len(self.prototypes) == 0:
            self.prototypes[1] = feat.copy()
            return 1

        if len(self.prototypes) == 1:
            d1 = self._distance(feat, self.prototypes[1])

            if d1 >= self.config.second_team_distance_threshold:
                self.prototypes[2] = feat.copy()
                return 2

            # עדיין רק קבוצה אחת ידועה
            p = self.prototypes[1]
            self.prototypes[1] = (1 - self.config.prototype_momentum) * p + self.config.prototype_momentum * feat
            return 1

        d1 = self._distance(feat, self.prototypes[1])
        d2 = self._distance(feat, self.prototypes[2])

        team_id = 1 if d1 <= d2 else 2
        p = self.prototypes[team_id]
        self.prototypes[team_id] = (1 - self.config.prototype_momentum) * p + self.config.prototype_momentum * feat
        return team_id

    def classify(self, frame, active_tracks: List[Dict]) -> List[Dict]:
        out = []

        for tr in active_tracks:
            item = dict(tr)
            feat = self._extract_jersey_feature(frame, tr["bbox"])

            if feat is None:
                item["team_id"] = None
                item["team_label"] = "unknown"
                out.append(item)
                continue

            team_id = self._assign_team_id(feat)
            item["team_id"] = team_id
            item["team_label"] = f"team_{team_id}"
            out.append(item)

        return out
