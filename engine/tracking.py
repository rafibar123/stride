from dataclasses import dataclass
from typing import List, Dict
import math


@dataclass
class TrackingConfig:
    max_distance: float = 90.0
    max_missed_frames: int = 25
    min_hits: int = 2


def euclidean(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


class Track:

    def __init__(self, track_id, bbox, frame_idx):
        self.track_id = track_id
        self.bbox = bbox
        self.center = self._center(bbox)
        self.last_frame = frame_idx
        self.hits = 1
        self.missed = 0

        self.history = []

    def _center(self, bbox):
        x1, y1, x2, y2 = bbox
        return [(x1 + x2) / 2, (y1 + y2) / 2]

    def update(self, bbox, frame_idx):
        self.bbox = bbox
        self.center = self._center(bbox)
        self.last_frame = frame_idx
        self.hits += 1
        self.missed = 0

        self.history.append({
            "frame": frame_idx,
            "x": self.center[0],
            "y": self.center[1],
            "track_id": self.track_id
        })

    def mark_missed(self):
        self.missed += 1


class SimpleByteTrackLikeTracker:

    def __init__(self, config: TrackingConfig):
        self.config = config
        self.tracks: List[Track] = []
        self.next_id = 1

    def _match(self, detections, frame_idx):

        assigned_tracks = set()
        assigned_dets = set()

        matches = []

        for t_idx, track in enumerate(self.tracks):

            best_det = None
            best_dist = 1e9

            for d_idx, det in enumerate(detections):

                if d_idx in assigned_dets:
                    continue

                bbox = det["bbox"]
                center = [
                    (bbox[0] + bbox[2]) / 2,
                    (bbox[1] + bbox[3]) / 2
                ]

                dist = euclidean(center, track.center)

                if dist < best_dist:
                    best_dist = dist
                    best_det = d_idx

            if best_det is None:
                continue

            if best_dist > self.config.max_distance:
                continue

            matches.append((t_idx, best_det))
            assigned_tracks.add(t_idx)
            assigned_dets.add(best_det)

        return matches, assigned_tracks, assigned_dets

    def update(self, detections: List[Dict], frame_idx: int):

        matches, assigned_tracks, assigned_dets = self._match(detections, frame_idx)

        for t_idx, d_idx in matches:
            self.tracks[t_idx].update(detections[d_idx]["bbox"], frame_idx)

        for t_idx, track in enumerate(self.tracks):
            if t_idx not in assigned_tracks:
                track.mark_missed()

        for d_idx, det in enumerate(detections):
            if d_idx not in assigned_dets:
                new_track = Track(
                    track_id=self.next_id,
                    bbox=det["bbox"],
                    frame_idx=frame_idx
                )
                self.next_id += 1
                self.tracks.append(new_track)

        self.tracks = [
            t for t in self.tracks
            if t.missed <= self.config.max_missed_frames
        ]

        active_tracks = []

        for t in self.tracks:
            if t.hits < self.config.min_hits:
                continue

            active_tracks.append({
                "track_id": t.track_id,
                "bbox": t.bbox,
                "center": t.center,
                "conf": 1.0
            })

        return active_tracks

    def export_tracks(self):

        out = []

        for t in self.tracks:
            out.extend(t.history)

        return out
