"""
Stride — Advanced per-player metrics.
Computed from raw track_history after the frame loop.

All metrics are derived from the tracked player's position sequence;
no extra AI calls needed.
"""

import math
from typing import Dict, List, Optional, Tuple

# Speed thresholds (m/s)
_SPRINT_MPS  = 5.0    # 18 km/h
_RUN_MPS     = 3.9    # 14 km/h — jogging/running boundary
_WALK_MPS    = 0.5    # 1.8 km/h — standing/walking boundary
_MAX_REAL    = 11.0   # cap: discard tracking artifacts above ~40 km/h

# Minimum pixel displacement per step to avoid noise when stationary
_MIN_PIXEL_MOVE = 3.0


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_time(sec: float) -> str:
    s = int(sec)
    m = s // 60
    return f"{m}:{s % 60:02d}"


def _step_speed(p0: Dict, p1: Dict, fps: float, meters_per_pixel: float) -> Optional[float]:
    """Return m/s between two track points, or None if it's a tracking artifact."""
    dt_frames = max(1, p1["frame"] - p0["frame"])
    dt = dt_frames / max(fps, 1e-6)

    if "pitch_x" in p0 and "pitch_x" in p1:
        dx = p1["pitch_x"] - p0["pitch_x"]
        dy = p1["pitch_y"] - p0["pitch_y"]
        dist = math.sqrt(dx * dx + dy * dy)
    else:
        cx0, cy0 = p0["center"][0], p0["center"][1]
        cx1, cy1 = p1["center"][0], p1["center"][1]
        dx = (cx1 - cx0) * meters_per_pixel
        dy = (cy1 - cy0) * meters_per_pixel
        dist = math.sqrt(dx * dx + dy * dy)

    spd = dist / max(dt, 1e-6)
    return spd if spd <= _MAX_REAL else None


# ── public entry point ────────────────────────────────────────────────────────

def compute_advanced_metrics(
    track_history: Dict[int, List[Dict]],
    target_track_id: int,
    fps: float,
    meters_per_pixel: float,
) -> Dict:
    """
    Compute advanced metrics for the target player.

    Returns a dict with keys:
      activity           – {standing_pct, walking_pct, running_pct}
      direction_changes  – int (agility count)
      sprint_recovery_avg_sec – float
      stamina_segments   – list of 5 {segment, label, intensity, sprint_count}
      stamina_insight    – str
      sprint_moments     – list of up to 3 {timestamp_sec, speed_kmh, label}
    """
    points = track_history.get(target_track_id, [])
    if len(points) < 3:
        return {}

    points = sorted(points, key=lambda p: p["frame"])

    # ── Per-step speed + timestamp sequence ───────────────────────────────────
    speed_seq: List[Tuple[float, float]] = []  # (timestamp_sec, speed_mps)

    for i in range(1, len(points)):
        spd = _step_speed(points[i - 1], points[i], fps, meters_per_pixel)
        if spd is None:
            continue
        ts = points[i - 1]["frame"] / max(fps, 1e-6)
        speed_seq.append((ts, spd))

    if not speed_seq:
        return {}

    speeds = [s for _, s in speed_seq]

    # ── 1. Activity breakdown ─────────────────────────────────────────────────
    n = len(speeds)
    standing = sum(1 for s in speeds if s < _WALK_MPS)
    walking  = sum(1 for s in speeds if _WALK_MPS <= s < _RUN_MPS)
    running  = sum(1 for s in speeds if s >= _RUN_MPS)

    activity = {
        "standing_pct": round(standing / n * 100),
        "walking_pct":  round(walking  / n * 100),
        "running_pct":  round(running  / n * 100),
    }

    # ── 2. Direction changes (agility) ────────────────────────────────────────
    dir_changes = 0
    for i in range(1, len(points) - 1):
        cx0, cy0 = points[i - 1]["center"][0], points[i - 1]["center"][1]
        cx1, cy1 = points[i    ]["center"][0], points[i    ]["center"][1]
        cx2, cy2 = points[i + 1]["center"][0], points[i + 1]["center"][1]

        vx1, vy1 = cx1 - cx0, cy1 - cy0
        vx2, vy2 = cx2 - cx1, cy2 - cy1
        mag1 = math.sqrt(vx1 * vx1 + vy1 * vy1)
        mag2 = math.sqrt(vx2 * vx2 + vy2 * vy2)

        if mag1 < _MIN_PIXEL_MOVE or mag2 < _MIN_PIXEL_MOVE:
            continue

        cos_a = (vx1 * vx2 + vy1 * vy2) / (mag1 * mag2)
        cos_a = max(-1.0, min(1.0, cos_a))
        if math.degrees(math.acos(cos_a)) > 45:
            dir_changes += 1

    # ── 3. Sprint events (used for recovery time + highlight moments) ─────────
    sprint_events: List[Tuple[float, float, float]] = []  # (start_ts, end_ts, peak_spd)
    in_sprint = False
    sprint_start = 0.0
    sprint_peak  = 0.0

    for ts, spd in speed_seq:
        if spd >= _SPRINT_MPS:
            if not in_sprint:
                in_sprint     = True
                sprint_start  = ts
                sprint_peak   = spd
            else:
                sprint_peak = max(sprint_peak, spd)
        else:
            if in_sprint:
                sprint_events.append((sprint_start, ts, sprint_peak))
            in_sprint = False

    if in_sprint:
        sprint_events.append((sprint_start, speed_seq[-1][0], sprint_peak))

    # Recovery time — gap between end of one sprint and start of the next
    sprint_recovery_avg_sec = 0.0
    if len(sprint_events) >= 2:
        gaps = [sprint_events[i][0] - sprint_events[i - 1][1]
                for i in range(1, len(sprint_events))
                if sprint_events[i][0] - sprint_events[i - 1][1] > 0]
        if gaps:
            sprint_recovery_avg_sec = round(sum(gaps) / len(gaps), 1)

    # ── 4. Stamina curve (5 segments) ─────────────────────────────────────────
    t_start = speed_seq[0][0]
    t_end   = speed_seq[-1][0]
    t_total = max(t_end - t_start, 1.0)
    seg_dur = t_total / 5

    stamina_segments = []
    for seg_idx in range(5):
        s0 = t_start + seg_idx * seg_dur
        s1 = s0 + seg_dur
        seg_spd = [spd for ts, spd in speed_seq if s0 <= ts < s1]

        avg_spd = sum(seg_spd) / len(seg_spd) if seg_spd else 0.0
        # Normalise: 5 m/s (sprint pace) = 100
        intensity = min(100, round(avg_spd / 5.0 * 100))

        seg_sprints = sum(1 for ts, spd in speed_seq
                          if s0 <= ts < s1 and spd >= _SPRINT_MPS)

        # Time label — use seconds for short clips, minutes for longer
        if t_total < 120:
            label = f"{s0 - t_start:.0f}–{s1 - t_start:.0f}s"
        else:
            label = f"{(s0 - t_start) / 60:.0f}–{(s1 - t_start) / 60:.0f} min"

        stamina_segments.append({
            "segment":      seg_idx + 1,
            "label":        label,
            "intensity":    intensity,
            "sprint_count": seg_sprints,
        })

    # Stamina insight — compare first half vs second half
    stamina_insight = ""
    if len(stamina_segments) == 5:
        early = (stamina_segments[0]["intensity"] + stamina_segments[1]["intensity"]) / 2
        late  = (stamina_segments[3]["intensity"] + stamina_segments[4]["intensity"]) / 2
        if early > 0:
            drop = round((early - late) / early * 100)
            if drop >= 20:
                stamina_insight = (
                    f"Your energy dropped ~{drop}% in the later stages — "
                    "work on endurance to maintain this intensity longer."
                )
            elif drop <= -15:
                stamina_insight = "You got stronger as the session progressed — excellent endurance!"
            else:
                stamina_insight = "Consistent energy levels throughout the session."

    # ── 5. Sprint highlight moments (top 3 by peak speed) ────────────────────
    sprint_moments = [
        {
            "timestamp_sec": round(start_ts),
            "speed_kmh":     round(peak_spd * 3.6, 1),
            "label":         _fmt_time(start_ts),
        }
        for start_ts, _, peak_spd in sprint_events
    ]
    sprint_moments.sort(key=lambda x: x["speed_kmh"], reverse=True)
    sprint_moments = sprint_moments[:3]

    return {
        "activity":                  activity,
        "direction_changes":         dir_changes,
        "sprint_recovery_avg_sec":   sprint_recovery_avg_sec,
        "stamina_segments":          stamina_segments,
        "stamina_insight":           stamina_insight,
        "sprint_moments":            sprint_moments,
    }
