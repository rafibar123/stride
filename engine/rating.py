"""
Stride — FIFA-style player performance rating (0-10).

Dimensions
----------
Physical     Pace (top speed), endurance (distance/min), work-rate (sprint freq)
Attacking    Forward presence (att-third %), forward runs, avg activity
Positioning  Zone balance, pitch spread (heatmap variance)
Pressing     Sprint frequency as closing-down proxy, defensive engagement

All computed from tracked movement data only — no manual tagging required.
"""

from typing import Dict, List, Optional


# ── benchmarks (what earns a 10) ─────────────────────────────────────────────
_PACE_MAX_KMH       = 36.0   # world-class sprint ≈ 36 km/h
_DIST_PER_MIN_HIGH  = 140.0  # m/min — elite youth ~ 120-150
_SPRINT_PER_MIN_MAX = 2.0    # 2 sprint bursts/min = 10


def _clamp(v: float, lo: float = 3.0, hi: float = 9.8) -> float:
    return round(max(lo, min(hi, v)), 1)


def _zone_pcts(
    zone_frames: Dict, heatmap_points: List, video_width: int
) -> tuple:
    """
    Return (def_pct, mid_pct, att_pct) as fractions 0-1.
    Falls back to pixel x-position estimation when pitch calibration is off
    (zone_frames all zeros).
    """
    df = zone_frames.get("defensive_third", 0)
    mf = zone_frames.get("middle_third", 0)
    af = zone_frames.get("attacking_third", 0)
    total = df + mf + af

    if total == 0 and heatmap_points:
        W = max(video_width, 1)
        for pt in heatmap_points:
            x = float(pt[0])
            if x < W / 3:
                df += 1
            elif x < 2 * W / 3:
                mf += 1
            else:
                af += 1
        total = df + mf + af

    total = max(total, 1)
    return df / total, mf / total, af / total


def _spread_score(pts: List) -> float:
    """
    Normalised 0-1 pitch coverage from heatmap point variance.
    High variance = good coverage = good score.
    """
    if len(pts) < 5:
        return 0.5
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = (sum((x - mx) ** 2 for x in xs) / n) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / n) ** 0.5
    # ~300 combined std = good spread for a 1080-wide frame
    return min((sx + sy) / 300.0, 1.0)


def compute_player_rating(
    player_metrics: Dict,
    fps: float,
    heatmap_points: Optional[List] = None,
    video_meta: Optional[Dict] = None,
) -> Dict:
    """
    Return FIFA-style rating dict:
      { overall, physical, attacking, positioning, pressing, breakdown }

    All sub-scores clamped to [3.0, 9.8] (realistic human range).
    """
    dist_m        = float(player_metrics.get("distance_m", 0.0))
    max_spd_mps   = float(player_metrics.get("max_speed_mps", 0.0))
    avg_spd_mps   = float(player_metrics.get("avg_speed_mps", 0.0))
    sprint_count  = int(player_metrics.get("sprint_count", 0))
    zone_frames   = player_metrics.get("zone_frames", {})
    total_frames  = max(int(player_metrics.get("total_frames", 1)), 1)

    duration_s    = total_frames / max(float(fps), 1.0)
    duration_min  = duration_s / 60.0

    vw = int((video_meta or {}).get("width", 1920))
    pts = heatmap_points or []

    def_pct, mid_pct, att_pct = _zone_pcts(zone_frames, pts, vw)

    # ── Physical ──────────────────────────────────────────────────────────────
    # Pace: top speed relative to human sprint ceiling
    pace_s = min(max_spd_mps * 3.6 / _PACE_MAX_KMH, 1.0)

    # Endurance: distance covered per minute of tracked time
    dist_per_min = dist_m / max(duration_min, 0.01)
    endurance_s  = min(dist_per_min / _DIST_PER_MIN_HIGH, 1.0)

    # Work rate: sprint frequency
    spm = sprint_count / max(duration_min, 0.01)
    workrate_s = min(spm / _SPRINT_PER_MIN_MAX, 1.0)

    physical = (pace_s * 0.30 + endurance_s * 0.45 + workrate_s * 0.25) * 10

    # ── Attacking ─────────────────────────────────────────────────────────────
    # Attacking third presence
    att_presence_s = att_pct  # 0-1

    # Purposeful movement (avg speed proxy for active forward play)
    avg_activity_s = min(avg_spd_mps / 3.5, 1.0)  # 3.5 m/s = highly active

    # Sprint volume as forward-run proxy
    sprint_vol_s = min(spm / (_SPRINT_PER_MIN_MAX * 0.75), 1.0)

    attacking = (att_presence_s * 0.40 + sprint_vol_s * 0.35 + avg_activity_s * 0.25) * 10

    # ── Positioning ───────────────────────────────────────────────────────────
    # Reward balanced forward distribution (ideal: 20% def / 45% mid / 35% att)
    balance_pen = abs(mid_pct - 0.40) + abs(att_pct - 0.35) * 0.6
    balance_s   = max(0.0, 1.0 - balance_pen)

    fwd_presence_s = mid_pct + att_pct  # forward > defensive = better

    spread_s = _spread_score(pts)

    positioning = (balance_s * 0.45 + fwd_presence_s * 0.35 + spread_s * 0.20) * 10

    # ── Pressing ─────────────────────────────────────────────────────────────
    # Sprint frequency ≈ closing-down intensity
    pressing_intensity_s = workrate_s

    # Defensive engagement (time in defensive third — shows defensive work)
    def_eng_s = min(def_pct * 2.5, 1.0)  # 40% in def third = full score

    # Effort level: penalty for low avg speed (standing still = not pressing)
    effort_s = min(avg_spd_mps / 1.5, 1.0)

    pressing = (pressing_intensity_s * 0.45 + def_eng_s * 0.30 + effort_s * 0.25) * 10

    # ── Overall (weighted) ────────────────────────────────────────────────────
    overall = (
        physical    * 0.35 +
        attacking   * 0.25 +
        positioning * 0.25 +
        pressing    * 0.15
    )

    return {
        "overall":     _clamp(overall),
        "physical":    _clamp(physical),
        "attacking":   _clamp(attacking),
        "positioning": _clamp(positioning),
        "pressing":    _clamp(pressing),
        "breakdown": {
            "pace_kmh":        round(max_spd_mps * 3.6, 1),
            "dist_per_min_m":  round(dist_per_min, 1),
            "sprints_per_min": round(spm, 2),
            "att_third_pct":   int(att_pct * 100),
            "def_third_pct":   int(def_pct * 100),
            "mid_third_pct":   int(mid_pct * 100),
            "duration_min":    round(duration_min, 1),
        },
    }
