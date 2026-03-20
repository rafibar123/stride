"""
Stride — Pass detection and accuracy tracking.

Algorithm
---------
1. Map ball positions and player foot positions to frame numbers.
2. Compute ball velocity between consecutive detected frames (real seconds).
3. Detect "kick" events: ball was near player's foot, then ball velocity spikes.
4. After each kick, scan ahead to see if the ball decelerates near another person
   (successful pass) or exits without a receiver (failed pass).

Everything is expressed in pixel-fractions of frame width so it works regardless
of resolution, camera angle or whether pitch calibration is active.
"""

from typing import Dict, List, Optional, Tuple


# ── tuneable constants ─────────────────────────────────────────────────────────

# Ball within this fraction of frame_width from player's foot = contact range
_NEAR_PLAYER_FRAC   = 0.08

# Ball speed above this fraction of frame_width per real-second = kicked ball
_KICK_VEL_FRAC      = 0.8

# Ball speed below this = ball has essentially stopped (km/h equivalent ~zero)
_RECEIVE_VEL_FRAC   = 0.18

# Potential receiver within this fraction of frame_width from stopped ball
_RECEIVE_DIST_FRAC  = 0.13

# How far ahead (in real seconds) to look for a ball receiver
_PASS_WINDOW_S      = 3.5

# Minimum real-time gap between two detected kick events (de-duplication)
_KICK_COOLDOWN_S    = 0.8

# Require ball velocity to spike within this many real-seconds after contact
_KICK_SPIKE_WINDOW_S = 0.6


# ── helpers ────────────────────────────────────────────────────────────────────

def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _build_ball_map(ball_track: List[Dict]) -> Dict[int, Dict]:
    """frame → ball dict (x, y)."""
    return {b["frame"]: b for b in ball_track if "x" in b and "y" in b}


def _build_player_foot_map(
    target_track_id: Optional[int],
    track_history: Dict[int, List[Dict]],
) -> Dict[int, Tuple[float, float]]:
    """frame → (foot_x, foot_y) for the target player."""
    result: Dict[int, Tuple[float, float]] = {}
    if target_track_id is None or target_track_id not in track_history:
        return result
    for pt in track_history[target_track_id]:
        bx1, by1, bx2, by2 = pt["bbox"]
        foot_x = (bx1 + bx2) / 2.0
        foot_y = by2
        result[pt["frame"]] = (foot_x, foot_y)
    return result


def _build_other_centers_map(
    target_track_id: Optional[int],
    track_history: Dict[int, List[Dict]],
) -> Dict[int, List[Tuple[float, float]]]:
    """frame → list of (cx, cy) for every tracked player except the target."""
    result: Dict[int, List[Tuple[float, float]]] = {}
    for tid, frames in track_history.items():
        if tid == target_track_id:
            continue
        for pt in frames:
            f = pt["frame"]
            result.setdefault(f, []).append(
                (float(pt["center"][0]), float(pt["center"][1]))
            )
    return result


def _compute_ball_velocities(
    ball_map: Dict[int, Dict],
    fps: float,
) -> Dict[int, float]:
    """
    Returns {frame: speed_px_per_second} for consecutive ball detections.
    Uses real frame intervals so frame_skip doesn't distort values.
    """
    vel: Dict[int, float] = {}
    sorted_frames = sorted(ball_map.keys())
    for i in range(1, len(sorted_frames)):
        f0, f1 = sorted_frames[i - 1], sorted_frames[i]
        dt = (f1 - f0) / max(fps, 1.0)
        if dt <= 0:
            continue
        b0, b1 = ball_map[f0], ball_map[f1]
        speed = _dist(b0["x"], b0["y"], b1["x"], b1["y"]) / dt
        vel[f1] = speed
    return vel


# ── main entry ─────────────────────────────────────────────────────────────────

def detect_passes(
    ball_track: List[Dict],
    target_track_id: Optional[int],
    track_history: Dict[int, List[Dict]],
    fps: float,
    frame_size: Tuple[int, int],
) -> Dict:
    """
    Detect pass events for the target player.

    Returns
    -------
    {
        "total":        int,   # kick events detected (passes + unknowns)
        "accurate":     int,   # ball received by a nearby player
        "failed":       int,   # ball not received (out / poor pass)
        "unknown":      int,   # couldn't determine outcome (video ended)
        "accuracy_pct": float, # accurate / max(total, 1) * 100
        "events":       list,  # [{frame, kick_frame, result}]
        "coach_note":   str,   # human-readable summary
    }
    """
    width, _height = frame_size
    if width <= 0:
        width = 1920

    near_thresh   = width * _NEAR_PLAYER_FRAC
    kick_vel      = width * _KICK_VEL_FRAC
    receive_vel   = width * _RECEIVE_VEL_FRAC
    receive_dist  = width * _RECEIVE_DIST_FRAC

    ball_map      = _build_ball_map(ball_track)
    foot_map      = _build_player_foot_map(target_track_id, track_history)
    other_centers = _build_other_centers_map(target_track_id, track_history)
    ball_vel      = _compute_ball_velocities(ball_map, fps)

    sorted_ball_frames = sorted(ball_map.keys())
    pass_window_frames = int(_PASS_WINDOW_S * fps)
    kick_cooldown_frames = int(_KICK_COOLDOWN_S * fps)
    kick_spike_window_frames = int(_KICK_SPIKE_WINDOW_S * fps)

    events: List[Dict] = []
    last_kick_frame = -99999

    for ball_frame in sorted_ball_frames:
        # ── is ball near player's foot? ───────────────────────────────────
        if ball_frame not in foot_map:
            continue
        fx, fy = foot_map[ball_frame]
        bx, by = ball_map[ball_frame]["x"], ball_map[ball_frame]["y"]

        if _dist(fx, fy, bx, by) > near_thresh:
            continue

        # ── is there a velocity spike in the next ~0.6 seconds? ──────────
        spike_frame = None
        look_end = ball_frame + kick_spike_window_frames
        for lf in sorted_ball_frames:
            if lf <= ball_frame:
                continue
            if lf > look_end:
                break
            if ball_vel.get(lf, 0) > kick_vel:
                spike_frame = lf
                break

        if spike_frame is None:
            continue

        # ── cooldown: ignore if another kick was just detected ────────────
        if spike_frame - last_kick_frame < kick_cooldown_frames:
            continue

        last_kick_frame = spike_frame

        # ── scan ahead for reception ──────────────────────────────────────
        result = "unknown"
        future_frames = [
            f for f in sorted_ball_frames
            if spike_frame < f <= spike_frame + pass_window_frames
        ]

        for ff in future_frames:
            v = ball_vel.get(ff, kick_vel)  # default = fast if no reading
            if v < receive_vel:
                # Ball has slowed — check for a nearby receiver
                bfx, bfy = ball_map[ff]["x"], ball_map[ff]["y"]
                receivers = other_centers.get(ff, [])
                received = any(
                    _dist(rx, ry, bfx, bfy) < receive_dist
                    for rx, ry in receivers
                )
                result = "accurate" if received else "failed"
                break

        events.append({
            "frame":      ball_frame,
            "kick_frame": spike_frame,
            "result":     result,
        })

    total    = len(events)
    accurate = sum(1 for e in events if e["result"] == "accurate")
    failed   = sum(1 for e in events if e["result"] == "failed")
    unknown  = total - accurate - failed
    pct      = round(accurate / max(total, 1) * 100, 1)

    return {
        "total":        total,
        "accurate":     accurate,
        "failed":       failed,
        "unknown":      unknown,
        "accuracy_pct": pct,
        "events":       events,
        "coach_note":   _coach_note(total, accurate, pct),
    }


def _coach_note(total: int, accurate: int, pct: float) -> str:
    if total < 3:
        return (
            "Not enough ball contact was detected to evaluate passing. "
            "Try a clip where you're more involved with the ball."
        )
    if pct >= 85:
        return (
            f"Your passing was excellent today — {accurate} out of {total} "
            f"passes found a teammate. Elite level decision-making."
        )
    if pct >= 70:
        return (
            f"Good passing performance — {accurate} of {total} passes were "
            f"accurate. A few sharper decisions could push this to elite level."
        )
    if pct >= 50:
        return (
            f"Mixed passing day — {accurate}/{total} passes connected. "
            f"Focus on picking simpler options under pressure."
        )
    return (
        f"Work on your passing — only {accurate}/{total} passes were "
        f"accurate today. Slow down and scan your options before the ball arrives."
    )
