"""
Stride — AI-powered match analysis.

Produces:
  - Positive/negative action counts (deterministic, from stats)
  - 3-sentence match summary  (Claude API → rule-based fallback)
  - 3 specific training drills (Claude API → rule-based fallback)

Set ANTHROPIC_API_KEY to enable the AI-generated path.
"""

import json
import logging
import os
from typing import Dict, List, Tuple

log = logging.getLogger("analysis")

# claude-haiku-4-5 is fast and cheap for per-analysis calls.
# Override with STRIDE_AI_MODEL env var if desired.
_MODEL = os.environ.get("STRIDE_AI_MODEL", "claude-haiku-4-5")


# ── Deterministic action counter ──────────────────────────────────────────────

def compute_actions(
    player_metrics: Dict,
    pass_stats: Dict,
    fps: float = 25.0,
) -> Dict:
    """
    Compute positive and negative actions from tracking data — no AI needed.

    Positive: successful passes, sprint bursts, good positioning, high work rate
    Negative: missed passes, wrong positioning, low activity, poor endurance
    """
    sprint_count = int(player_metrics.get("sprint_count", 0))
    avg_spd      = float(player_metrics.get("avg_speed_mps", 0.0))
    dist_m       = float(player_metrics.get("distance_m", 0.0))
    total_frames = max(int(player_metrics.get("total_frames", 1)), 1)
    zone_frames  = player_metrics.get("zone_frames", {})

    zd = zone_frames.get("defensive_third", 0)
    zm = zone_frames.get("middle_third", 0)
    za = zone_frames.get("attacking_third", 0)
    zt = max(zd + zm + za, 1)
    def_pct = zd / zt
    mid_pct = zm / zt
    att_pct = za / zt

    accurate     = int(pass_stats.get("accurate", 0))
    failed       = int(pass_stats.get("failed", 0))
    total_passes = int(pass_stats.get("total", 0))

    duration_min = (total_frames / max(fps, 1.0)) / 60.0

    pos: List[Dict] = []
    neg: List[Dict] = []

    # ── Passes ────────────────────────────────────────────────────────────────
    for _ in range(accurate):
        pos.append({"type": "successful_pass",  "label": "Successful pass"})
    for _ in range(failed):
        neg.append({"type": "missed_pass",       "label": "Missed / lost pass"})

    # ── Sprint bursts ─────────────────────────────────────────────────────────
    for _ in range(sprint_count):
        pos.append({"type": "sprint",            "label": "Sprint burst (≥18 km/h)"})

    # ── Positioning ───────────────────────────────────────────────────────────
    if att_pct >= 0.30:
        pos.append({"type": "good_positioning",  "label": "Good attacking presence"})
    if mid_pct >= 0.40:
        pos.append({"type": "good_positioning",  "label": "Strong midfield coverage"})
    if def_pct >= 0.50:
        neg.append({"type": "wrong_position",    "label": "Too deep — stuck in defensive third"})
    elif def_pct >= 0.40 and att_pct < 0.20:
        neg.append({"type": "wrong_position",    "label": "Poor forward positioning"})

    # ── Work rate & endurance ─────────────────────────────────────────────────
    if avg_spd >= 2.0:
        pos.append({"type": "high_activity",     "label": "High work rate"})
    elif avg_spd < 1.0:
        neg.append({"type": "slow_reaction",     "label": "Low activity / slow reactions"})

    if duration_min > 0.1:
        dist_per_min = dist_m / duration_min
        if dist_per_min >= 110:
            pos.append({"type": "ball_recovery", "label": "Excellent distance covered"})
        elif dist_per_min < 60:
            neg.append({"type": "low_endurance", "label": "Low distance covered"})

    return {
        "positive_count": len(pos),
        "negative_count":  len(neg),
        "positive_items":  pos,
        "negative_items":  neg,
    }


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_match_analysis(result_dict: Dict) -> Dict:
    """
    Build the full match analysis dict from a completed pipeline result.

    Returns:
    {
        "actions":         {positive_count, negative_count, positive_items, negative_items},
        "summary":         [str, str, str],                  # 3-sentence match summary
        "recommendations": [{drill, duration, focus}, ...],  # 3 training drills
        "ai_generated":    bool,
    }
    """
    per_player  = result_dict.get("per_player_metrics", [])
    player      = per_player[0] if per_player else {}
    pass_stats  = result_dict.get("pass_stats", {}) or {}
    rating      = result_dict.get("rating", {})  or {}
    fps         = float(result_dict.get("fps", 25.0))
    player_info = result_dict.get("player_info", {}) or {}

    actions = compute_actions(player, pass_stats, fps)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            summary, recs = _call_claude(player, pass_stats, rating, actions, player_info, fps)
            return {
                "actions":         actions,
                "summary":         summary,
                "recommendations": recs,
                "ai_generated":    True,
            }
        except Exception as exc:
            log.warning("Claude API call failed — using rule-based fallback: %s", exc)

    summary, recs = _rule_based(player, pass_stats, rating, fps)
    return {
        "actions":         actions,
        "summary":         summary,
        "recommendations": recs,
        "ai_generated":    False,
    }


# ── Claude API path ───────────────────────────────────────────────────────────

def _call_claude(
    player: Dict,
    pass_stats: Dict,
    rating: Dict,
    actions: Dict,
    player_info: Dict,
    fps: float,
) -> Tuple[List[str], List[Dict]]:
    import anthropic

    total_frames  = max(int(player.get("total_frames", 1)), 1)
    duration_min  = (total_frames / max(fps, 1.0)) / 60.0
    dist_m        = float(player.get("distance_m", 0.0))
    max_kmh       = float(player.get("max_speed_mps", 0.0)) * 3.6
    avg_kmh       = float(player.get("avg_speed_mps", 0.0)) * 3.6
    sprint_count  = int(player.get("sprint_count", 0))
    zone_frames   = player.get("zone_frames", {})
    zd  = zone_frames.get("defensive_third", 0)
    zm  = zone_frames.get("middle_third",    0)
    za  = zone_frames.get("attacking_third", 0)
    zt  = max(zd + zm + za, 1)

    pass_total    = int(pass_stats.get("total", 0))
    pass_accurate = int(pass_stats.get("accurate", 0))
    pass_pct      = float(pass_stats.get("accuracy_pct", 0.0))
    has_pass      = pass_total >= 3

    player_name = player_info.get("name", "the player") or "the player"
    team_name   = player_info.get("teamName", "") or ""

    pass_line = (
        f"{pass_accurate}/{pass_total} passes accurate ({pass_pct:.0f}%)"
        if has_pass else "Ball contact not detected"
    )

    stats_text = f"""Player: {player_name}{(' — ' + team_name) if team_name else ''}
Duration analysed: {duration_min:.1f} min
Distance covered: {dist_m:.0f} m ({dist_m / 1000:.2f} km)
Top speed: {max_kmh:.1f} km/h  |  Average speed: {avg_kmh:.1f} km/h
Sprint bursts (≥18 km/h): {sprint_count}
Zone: {zd / zt * 100:.0f}% def / {zm / zt * 100:.0f}% mid / {za / zt * 100:.0f}% att
Passing: {pass_line}
Actions: {actions['positive_count']} positive  /  {actions['negative_count']} negative
Rating: {rating.get('overall', 0):.1f}/10  \
(Phy {rating.get('physical', 0):.1f}  Att {rating.get('attacking', 0):.1f}  \
Pos {rating.get('positioning', 0):.1f}  Prs {rating.get('pressing', 0):.1f}  \
Pas {rating.get('passing', 0):.1f})"""

    schema = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Exactly 3 sentences: "
                    "[1] overall session summary with specific stats, "
                    "[2] best strength / highlight moment, "
                    "[3] main weakness or focus area"
                ),
            },
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "drill":    {"type": "string", "description": "Name of the training drill"},
                        "duration": {"type": "string", "description": "e.g. '20 minutes'"},
                        "focus":    {"type": "string", "description": "Short reason / what it improves"},
                    },
                    "required": ["drill", "duration", "focus"],
                    "additionalProperties": False,
                },
                "description": "Exactly 3 specific training recommendations tailored to this player's weaknesses",
            },
        },
        "required": ["summary", "recommendations"],
        "additionalProperties": False,
    }

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=1200,
        system=(
            "You are a professional football performance analyst and personal coach. "
            "Write directly to the player ('You ran…', 'Your passing…'). "
            "Be specific — reference the real numbers given. "
            "Be motivating but honest. Keep each sentence to 1-2 lines. "
            "Respond with valid JSON only — no prose, no markdown fences."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Analyse this session:\n\n{stats_text}\n\n"
                "Return this JSON (summary: exactly 3 strings, "
                "recommendations: exactly 3 objects with drill/duration/focus)."
            ),
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )

    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)

    summary = data.get("summary", [])[:3]
    recs    = data.get("recommendations", [])[:3]

    # Pad if the model returns fewer items (shouldn't happen but be defensive)
    while len(summary) < 3:
        summary.append("Analysis unavailable.")
    while len(recs) < 3:
        recs.append({"drill": "General fitness", "duration": "15 minutes", "focus": "Overall conditioning"})

    return summary, recs


# ── Rule-based fallback ───────────────────────────────────────────────────────

def _rule_based(
    player: Dict,
    pass_stats: Dict,
    rating: Dict,
    fps: float,
) -> Tuple[List[str], List[Dict]]:
    total_frames = max(int(player.get("total_frames", 1)), 1)
    duration_min = (total_frames / max(fps, 1.0)) / 60.0
    dist_m       = float(player.get("distance_m", 0.0))
    max_kmh      = float(player.get("max_speed_mps", 0.0)) * 3.6
    avg_kmh      = float(player.get("avg_speed_mps", 0.0)) * 3.6
    sprint_count = int(player.get("sprint_count", 0))
    zone_frames  = player.get("zone_frames", {})
    zd  = zone_frames.get("defensive_third", 0)
    zm  = zone_frames.get("middle_third",    0)
    za  = zone_frames.get("attacking_third", 0)
    zt  = max(zd + zm + za, 1)
    def_pct = zd / zt * 100
    mid_pct = zm / zt * 100
    att_pct = za / zt * 100

    pass_total    = int(pass_stats.get("total", 0))
    pass_accurate = int(pass_stats.get("accurate", 0))
    pass_pct      = float(pass_stats.get("accuracy_pct", 0.0))
    has_pass      = pass_total >= 3

    overall  = float(rating.get("overall", 0.0))
    dist_km  = dist_m / 1000
    dist_per_min = dist_m / max(duration_min, 0.01)

    # ── Sentence 1: Overall ───────────────────────────────────────────────────
    if overall >= 8.0:
        s1 = (f"Outstanding session — your {overall:.1f}/10 rating reflects {dist_km:.2f} km "
              f"covered and a top speed of {max_kmh:.1f} km/h.")
    elif overall >= 6.5:
        s1 = (f"Solid performance today. You covered {dist_km:.2f} km at an average of "
              f"{avg_kmh:.1f} km/h and earned a rating of {overall:.1f}/10.")
    else:
        s1 = (f"A building session with room to grow — {dist_km:.2f} km covered, "
              f"rating {overall:.1f}/10. Push harder in the next session.")

    # ── Sentence 2: Best strength ─────────────────────────────────────────────
    candidates = []
    if has_pass and pass_pct >= 75:
        candidates.append(f"Your passing stood out — {pass_accurate}/{pass_total} "
                          f"passes accurate ({pass_pct:.0f}%), showing clean decision-making.")
    if sprint_count >= 5:
        candidates.append(f"You showed real pace with {sprint_count} sprint bursts above "
                          f"18 km/h, reaching {max_kmh:.1f} km/h at your best.")
    if att_pct >= 35:
        candidates.append(f"You were a constant attacking threat, spending {att_pct:.0f}% "
                          f"of your time in the final third.")
    if dist_per_min >= 110:
        candidates.append(f"Your work rate was excellent — covering {dist_per_min:.0f} m/min "
                          f"shows real match fitness.")

    s2 = candidates[0] if candidates else (
        f"You covered all three zones — {def_pct:.0f}% defensive, "
        f"{mid_pct:.0f}% midfield, {att_pct:.0f}% attacking — showing solid awareness."
    )

    # ── Sentence 3: Main weakness ─────────────────────────────────────────────
    weaknesses = []
    if has_pass and pass_pct < 60:
        weaknesses.append(f"Work on your passing — only {pass_accurate}/{pass_total} "
                          f"passes connected today; better decision-making under pressure is key.")
    if sprint_count < 2 and duration_min > 1.0:
        weaknesses.append("You need more explosive runs — sprint count was low; "
                          "challenge yourself to make forward bursts every 2-3 minutes.")
    if att_pct < 20 and def_pct > 45:
        weaknesses.append(f"You spent too much time in your own half ({def_pct:.0f}% defensive); "
                          "make more forward runs to support attacks.")
    if avg_kmh < 1.5:
        weaknesses.append("Stay on the move throughout — your average work rate was below "
                          "optimal; don't let yourself stand still for long periods.")

    s3 = weaknesses[0] if weaknesses else (
        "Keep working on consistency across all phases — maintaining this level for "
        "the full match duration is your next target."
    )

    summary = [s1, s2, s3]

    # ── Training recommendations ──────────────────────────────────────────────
    drills: List[Dict] = []

    if has_pass and pass_pct < 65:
        drills.append({"drill": "Rondo passing drill (5v2)",
                       "duration": "20 minutes",
                       "focus": "Short passing accuracy and composure under pressure"})
    elif has_pass and pass_pct < 80:
        drills.append({"drill": "Two-touch passing with wall",
                       "duration": "15 minutes",
                       "focus": "Clean ball distribution and quick thinking"})

    if sprint_count < 3:
        drills.append({"drill": "10 × 30 m sprint intervals",
                       "duration": "15 minutes",
                       "focus": "Explosive acceleration and sprint capacity"})

    if def_pct > 45 or att_pct < 20:
        drills.append({"drill": "Shadow play — forward runs and overlaps",
                       "duration": "20 minutes",
                       "focus": "Reading the game and timing attacking movements"})

    if dist_per_min < 70:
        drills.append({"drill": "5 km interval run (1 min fast / 1 min jog)",
                       "duration": "25 minutes",
                       "focus": "Aerobic base and match stamina"})

    if max_kmh < 22:
        drills.append({"drill": "Resistance band acceleration + flying 20 m sprints",
                       "duration": "15 minutes",
                       "focus": "Top-end speed development"})

    # Guarantee 3 entries with generic fillers
    generic = [
        {"drill": "Small-sided 4v4 game",
         "duration": "20 minutes",
         "focus": "Match intensity, decision-making and pressing"},
        {"drill": "Ball control juggling + first touch",
         "duration": "15 minutes",
         "focus": "Technical ability on the ball"},
        {"drill": "Cool-down stretch + foam roll",
         "duration": "10 minutes",
         "focus": "Recovery, mobility and injury prevention"},
    ]
    for g in generic:
        if len(drills) >= 3:
            break
        drills.append(g)

    return summary, drills[:3]
