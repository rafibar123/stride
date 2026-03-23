from dataclasses import dataclass
from typing import List, Dict, Optional
from ultralytics import YOLO


@dataclass
class DetectionConfig:
    # yolov8x at 1280px: highest accuracy for player detection on GPU.
    # Ball uses 640px — fine detail at higher res rarely helps vs. speed cost.
    player_model: str = "yolov8x.pt"
    ball_model: str = "yolov8x.pt"
    player_conf: float = 0.22     # slightly lower — yolov8x is more precise so fewer FP
    ball_conf: float = 0.06       # lower for ball: harder to detect, FP filtered by class
    player_imgsz: int = 1280      # higher res catches distant players
    ball_imgsz: int = 640         # ball detection stays at 640 (adequate)
    person_class_id: int = 0
    sports_ball_class_id: int = 32
    # Ignore detections whose centre is in the top N% of the frame.
    # Filters crowd / stands noise in angled-camera footage (e.g. TikTok).
    min_y_ratio: float = 0.25


class Detector:
    """
    Detector יציב לכדורגל:
    - זיהוי שחקנים עם threshold נמוך יותר כדי לא לפספס דמויות רחוקות
    - זיהוי כדור עם מודל נפרד
    - הגנות מלאות למקרים של boxes ריקים / None / שגיאות מודל
    """

    def __init__(self, config: DetectionConfig):
        self.config = config
        self.player_model = YOLO(config.player_model)
        self.ball_model = YOLO(config.ball_model)

    def _safe_boxes_to_numpy(self, results):
        if results is None:
            return None, None, None

        if getattr(results, "boxes", None) is None:
            return None, None, None

        boxes_obj = results.boxes
        if boxes_obj is None:
            return None, None, None

        if getattr(boxes_obj, "xyxy", None) is None:
            return None, None, None

        try:
            boxes = boxes_obj.xyxy.cpu().numpy()
            classes = boxes_obj.cls.cpu().numpy() if getattr(boxes_obj, "cls", None) is not None else None
            confs = boxes_obj.conf.cpu().numpy() if getattr(boxes_obj, "conf", None) is not None else None
            return boxes, classes, confs
        except Exception:
            return None, None, None

    def detect_players(self, frame) -> List[Dict]:
        out: List[Dict] = []

        if frame is None:
            return out

        try:
            result = self.player_model(
                frame,
                conf=self.config.player_conf,
                imgsz=self.config.player_imgsz,
                verbose=False
            )[0]
        except Exception:
            return out

        boxes, classes, confs = self._safe_boxes_to_numpy(result)
        if boxes is None or classes is None or confs is None:
            return out

        frame_h = frame.shape[0] if frame is not None else 0
        min_y   = frame_h * self.config.min_y_ratio

        for box, cls, conf in zip(boxes, classes, confs):
            try:
                if int(cls) != self.config.person_class_id:
                    continue

                if float(conf) < self.config.player_conf:
                    continue

                x1, y1, x2, y2 = box.tolist()

                if x2 <= x1 or y2 <= y1:
                    continue

                # reject detections whose centre sits in the top N% of the
                # frame — these are crowd / stands / background, not players
                centre_y = (y1 + y2) / 2.0
                if centre_y < min_y:
                    continue

                out.append({
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "conf": float(conf),
                    "label": "player"
                })
            except Exception:
                continue

        return out

    def detect_and_track(self, frame, frame_idx: int) -> List[Dict]:
        """Detect and track players using BoT-SORT via ultralytics persist mode.

        BoT-SORT adds appearance-based ReID on top of ByteTrack kinematics:
        when a player exits and re-enters the frame the same track_id is
        preserved, preventing split metrics and wrong-player attribution.
        """
        out: List[Dict] = []
        if frame is None:
            return out

        try:
            results = self.player_model.track(
                frame,
                conf=self.config.player_conf,
                imgsz=self.config.player_imgsz,
                persist=True,
                tracker="botsort.yaml",
                verbose=False,
                classes=[self.config.person_class_id],
            )[0]
        except Exception:
            return out

        if results is None or getattr(results, "boxes", None) is None:
            return out

        boxes_obj = results.boxes
        if boxes_obj is None or getattr(boxes_obj, "xyxy", None) is None:
            return out

        try:
            xyxy = boxes_obj.xyxy.cpu().numpy()
            confs = boxes_obj.conf.cpu().numpy() if getattr(boxes_obj, "conf", None) is not None else None
            ids = getattr(boxes_obj, "id", None)
            track_ids = ids.cpu().numpy().astype(int) if ids is not None else None
        except Exception:
            return out

        if xyxy is None or confs is None:
            return out

        frame_h = frame.shape[0]
        min_y = frame_h * self.config.min_y_ratio

        for i, (box, conf) in enumerate(zip(xyxy, confs)):
            try:
                if float(conf) < self.config.player_conf:
                    continue
                x1, y1, x2, y2 = box.tolist()
                if x2 <= x1 or y2 <= y1:
                    continue
                if (y1 + y2) / 2.0 < min_y:
                    continue
                track_id = int(track_ids[i]) if track_ids is not None else i
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                out.append({
                    "track_id": track_id,
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "center": [float(cx), float(cy)],
                    "conf": float(conf),
                    "label": "player",
                    "frame": frame_idx,
                })
            except Exception:
                continue

        return out

    def detect_ball(self, frame) -> Optional[Dict]:
        if frame is None:
            return None

        try:
            result = self.ball_model(
                frame,
                conf=self.config.ball_conf,
                imgsz=self.config.ball_imgsz,
                verbose=False
            )[0]
        except Exception:
            return None

        boxes, classes, confs = self._safe_boxes_to_numpy(result)
        if boxes is None or classes is None or confs is None:
            return None

        best_ball = None
        best_conf = -1.0

        for box, cls, conf in zip(boxes, classes, confs):
            try:
                if int(cls) != self.config.sports_ball_class_id:
                    continue

                if float(conf) < self.config.ball_conf:
                    continue

                x1, y1, x2, y2 = box.tolist()
                if x2 <= x1 or y2 <= y1:
                    continue

                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0

                if float(conf) > best_conf:
                    best_ball = {
                        "bbox": [float(x1), float(y1), float(x2), float(y2)],
                        "center": [float(cx), float(cy)],
                        "conf": float(conf),
                        "label": "ball"
                    }
                    best_conf = float(conf)
            except Exception:
                continue

        return best_ball
