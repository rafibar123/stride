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
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("analysis")

# claude-haiku-4-5 is fast and cheap for per-analysis calls.
# Override with STRIDE_AI_MODEL env var if desired.
_MODEL = os.environ.get("STRIDE_AI_MODEL", "claude-haiku-4-5")


# ── Deterministic action counter ──────────────────────────────────────────────

def compute_actions(
    player_metrics: Dict,
    pass_stats: Dict,
    fps: float = 25.0,
    manual_stats: Optional[Dict] = None,
) -> Dict:
    """
    Compute positive and negative actions from tracking data — no AI needed.

    Positive: successful passes, sprint bursts, good positioning, high work rate,
              ball recoveries (manual), shots on goal (manual)
    Negative: missed passes, wrong positioning, low activity, lost balls (manual)

    manual_stats keys (all optional):
        passes_made, passes_successful, shots_on_goal, ball_recoveries, lost_balls
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

    duration_min = (total_frames / max(fps, 1.0)) / 60.0

    # ── Pass counts: manual overrides AI-detected when provided ───────────────
    ms = manual_stats or {}
    manual_total = int(ms.get("passes_made", 0))
    manual_acc   = int(ms.get("passes_successful", 0))

    if manual_total > 0:
        accurate = min(manual_acc, manual_total)
        failed   = manual_total - accurate
    else:
        accurate = int(pass_stats.get("accurate", 0))
        failed   = int(pass_stats.get("failed",   0))

    pos: List[Dict] = []
    neg: List[Dict] = []

    # ── Passes ────────────────────────────────────────────────────────────────
    for _ in range(accurate):
        pos.append({"type": "successful_pass",  "label": "Successful pass"})
    for _ in range(failed):
        neg.append({"type": "missed_pass",       "label": "Missed / lost pass"})

    # ── Manual-only items ─────────────────────────────────────────────────────
    for _ in range(int(ms.get("ball_recoveries", 0))):
        pos.append({"type": "ball_recovery",    "label": "Ball recovery"})
    for _ in range(int(ms.get("shots_on_goal", 0))):
        pos.append({"type": "shot_on_goal",     "label": "Shot on goal"})
    for _ in range(int(ms.get("lost_balls", 0))):
        neg.append({"type": "lost_ball",         "label": "Lost the ball"})
    for _ in range(int(ms.get("aerial_duels_won", 0))):
        pos.append({"type": "aerial_duel_won",   "label": "Aerial duel won"})
    aerial_lost = max(0, int(ms.get("aerial_duels_total", 0)) - int(ms.get("aerial_duels_won", 0)))
    for _ in range(aerial_lost):
        neg.append({"type": "aerial_duel_lost",  "label": "Aerial duel lost"})
    for _ in range(int(ms.get("received_under_pressure", 0))):
        pos.append({"type": "received_pressure", "label": "Received ball under pressure"})
    for _ in range(int(ms.get("created_space", 0))):
        pos.append({"type": "created_space",     "label": "Created space for teammate"})

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

def generate_match_analysis(
    result_dict: Dict,
    manual_stats: Optional[Dict] = None,
) -> Dict:
    """
    Build the full match analysis dict from a completed pipeline result.

    manual_stats (optional): player-reported numbers that override/extend
        AI-detected data — keys: passes_made, passes_successful,
        shots_on_goal, ball_recoveries, lost_balls.

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

    actions      = compute_actions(player, pass_stats, fps, manual_stats)
    player_style = _compute_player_style(player, pass_stats, rating, manual_stats)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            summary, recs = _call_claude(
                player, pass_stats, rating, actions, player_info, fps, manual_stats
            )
            return {
                "actions":         actions,
                "summary":         summary,
                "recommendations": recs,
                "ai_generated":    True,
                "player_style":    player_style,
            }
        except Exception as exc:
            log.warning("Claude API call failed — using rule-based fallback: %s", exc)

    summary, recs = _rule_based(player, pass_stats, rating, fps, manual_stats)
    return {
        "actions":         actions,
        "summary":         summary,
        "recommendations": recs,
        "ai_generated":    False,
        "player_style":    player_style,
    }


# ── Claude API path ───────────────────────────────────────────────────────────

def _call_claude(
    player: Dict,
    pass_stats: Dict,
    rating: Dict,
    actions: Dict,
    player_info: Dict,
    fps: float,
    manual_stats: Optional[Dict] = None,
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

    player_name = player_info.get("name", "the player") or "the player"
    team_name   = player_info.get("teamName", "") or ""

    # Resolve pass line — prefer manual input if provided
    ms = manual_stats or {}
    manual_total = int(ms.get("passes_made", 0))
    manual_acc   = int(ms.get("passes_successful", 0))
    if manual_total > 0:
        manual_pct = round(manual_acc / manual_total * 100)
        pass_line  = f"{manual_acc}/{manual_total} passes accurate ({manual_pct}%) [player-reported]"
        has_pass   = True
    else:
        pass_total    = int(pass_stats.get("total", 0))
        pass_accurate = int(pass_stats.get("accurate", 0))
        pass_pct      = float(pass_stats.get("accuracy_pct", 0.0))
        has_pass      = pass_total >= 3
        pass_line = (
            f"{pass_accurate}/{pass_total} passes accurate ({pass_pct:.0f}%)"
            if has_pass else "Ball contact not detected"
        )

    shots_line     = f"Shots on goal: {ms['shots_on_goal']}" if ms.get("shots_on_goal") else ""
    recovery_line  = f"Ball recoveries: {ms['ball_recoveries']}" if ms.get("ball_recoveries") else ""
    lostball_line  = f"Lost balls: {ms['lost_balls']}" if ms.get("lost_balls") else ""
    manual_block   = "\n".join(l for l in [shots_line, recovery_line, lostball_line] if l)

    stats_text = f"""Player: {player_name}{(' — ' + team_name) if team_name else ''}
Duration analysed: {duration_min:.1f} min
Distance covered: {dist_m:.0f} m ({dist_m / 1000:.2f} km)
Top speed: {max_kmh:.1f} km/h  |  Average speed: {avg_kmh:.1f} km/h
Sprint bursts (≥18 km/h): {sprint_count}
Zone: {zd / zt * 100:.0f}% def / {zm / zt * 100:.0f}% mid / {za / zt * 100:.0f}% att
Passing: {pass_line}{chr(10) + manual_block if manual_block else ''}
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
                        "name":             {"type": "string",  "description": "Short drill name, e.g. '6 × 30 m sprint intervals'"},
                        "duration_minutes": {"type": "integer", "description": "Duration in minutes, e.g. 15"},
                        "goal":             {"type": "string",  "description": "One sentence: what physical/technical quality this targets"},
                        "instructions":     {"type": "string",  "description": "2-3 sentences explaining exactly how to perform the drill"},
                        "difficulty":       {"type": "string",  "enum": ["easy", "medium", "hard"]},
                    },
                    "required": ["name", "duration_minutes", "goal", "instructions", "difficulty"],
                    "additionalProperties": False,
                },
                "description": (
                    "3 to 5 personalised training drills that directly address the weaknesses "
                    "seen in the stats. Each must be actionable and specific."
                ),
            },
        },
        "required": ["summary", "recommendations"],
        "additionalProperties": False,
    }

    client = anthropic.Anthropic(timeout=25.0)  # never hang longer than 25s
    response = client.messages.create(
        model=_MODEL,
        max_tokens=1800,
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
                "recommendations: 3–5 personalised drills with name/duration_minutes/goal/instructions/difficulty)."
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
    recs    = data.get("recommendations", [])[:5]

    _FALLBACK_DRILL = {
        "name": "General fitness circuit",
        "duration_minutes": 15,
        "goal": "Maintain aerobic base and overall conditioning.",
        "instructions": "Alternate 1 min jogging with 30 s of bodyweight exercises (squats, push-ups, lunges). Repeat 5 rounds.",
        "difficulty": "medium",
    }
    # Pad if the model returns fewer items (shouldn't happen but be defensive)
    while len(summary) < 3:
        summary.append("Analysis unavailable.")
    while len(recs) < 3:
        recs.append(_FALLBACK_DRILL)

    return summary, recs


# ── Rule-based fallback ───────────────────────────────────────────────────────

def _rule_based(
    player: Dict,
    pass_stats: Dict,
    rating: Dict,
    fps: float,
    manual_stats: Optional[Dict] = None,
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

    # Pass data — prefer manual if provided
    ms = manual_stats or {}
    manual_total = int(ms.get("passes_made", 0))
    manual_acc   = int(ms.get("passes_successful", 0))
    if manual_total > 0:
        pass_total    = manual_total
        pass_accurate = min(manual_acc, manual_total)
        pass_pct      = pass_accurate / pass_total * 100
        has_pass      = True
    else:
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
        drills.append({
            "name": "Rondo passing drill (5v2)",
            "duration_minutes": 20,
            "goal": "Improve short passing accuracy and decision-making under pressure.",
            "instructions": (
                "Form a circle of 5 players with 2 defenders in the middle. "
                "Keep the ball moving with one or two touches only. "
                "When a defender wins the ball, the player who lost it swaps in."
            ),
            "difficulty": "medium",
        })
    elif has_pass and pass_pct < 80:
        drills.append({
            "name": "Two-touch passing with wall",
            "duration_minutes": 15,
            "goal": "Sharpen first touch and clean one-two distribution.",
            "instructions": (
                "Stand 4 m from a wall. Pass firmly, control the rebound with one touch, "
                "then pass again. Alternate feet every 2 minutes. "
                "Progress to moving laterally between each rep."
            ),
            "difficulty": "easy",
        })

    if sprint_count < 3:
        drills.append({
            "name": "6 × 30 m sprint intervals",
            "duration_minutes": 15,
            "goal": "Build explosive acceleration and sprint capacity.",
            "instructions": (
                "Mark out 30 m. Sprint at 100% effort, walk back as recovery. "
                "Rest 90 s between sets. Focus on driving knees high and staying low in the first 10 m."
            ),
            "difficulty": "hard",
        })

    if def_pct > 45 or att_pct < 20:
        drills.append({
            "name": "Forward-run shadow play",
            "duration_minutes": 20,
            "goal": "Develop timing of attacking runs and positioning in the final third.",
            "instructions": (
                "Without defenders, walk through team shape then trigger forward runs on coach's signal. "
                "Practise overlap runs, diagonal cuts into the box, and late arrivals. "
                "Repeat 8–10 times focusing on movement timing."
            ),
            "difficulty": "easy",
        })

    if dist_per_min < 70:
        drills.append({
            "name": "5 km tempo run (1 min fast / 1 min jog)",
            "duration_minutes": 25,
            "goal": "Raise aerobic base and match endurance.",
            "instructions": (
                "Alternate 1 min at 80% effort with 1 min of light jogging. "
                "Complete 12 rounds. Track total distance and aim to improve each session."
            ),
            "difficulty": "medium",
        })

    if max_kmh < 22:
        drills.append({
            "name": "Resistance band acceleration + flying 20 m sprints",
            "duration_minutes": 15,
            "goal": "Develop top-end speed and stride power.",
            "instructions": (
                "Attach resistance band around waist (partner holds). "
                "Do 3 × 20 m resisted sprints, then immediately 3 × 20 m free sprints. "
                "Rest 2 min between sets."
            ),
            "difficulty": "hard",
        })

    # Guarantee at least 3 entries with generic fillers
    generic = [
        {
            "name": "Small-sided 4v4 game",
            "duration_minutes": 20,
            "goal": "Simulate match intensity and sharpen pressing and decision-making.",
            "instructions": (
                "Play 4v4 on a 30 × 20 m pitch with small goals. "
                "Press immediately on losing the ball. "
                "Rotate players every 4 minutes."
            ),
            "difficulty": "medium",
        },
        {
            "name": "Ball juggling + first-touch control",
            "duration_minutes": 15,
            "goal": "Improve touch quality and ball confidence.",
            "instructions": (
                "Juggle for 1 min, then catch and throw high — control the drop with one touch. "
                "Progress to volleying against a wall. "
                "Aim for zero dead touches."
            ),
            "difficulty": "easy",
        },
        {
            "name": "Cool-down stretch + foam roll",
            "duration_minutes": 10,
            "goal": "Speed up recovery and maintain mobility.",
            "instructions": (
                "5 min of light jogging, then foam roll quads, hamstrings and calves (30 s each). "
                "Finish with hip-flexor and groin static stretches held 30 s."
            ),
            "difficulty": "easy",
        },
    ]
    for g in generic:
        if len(drills) >= 5:
            break
        drills.append(g)

    return summary, drills[:5]


# ── Coach / team analysis ─────────────────────────────────────────────────────

def generate_coach_analysis(result_dict: Dict) -> Dict:
    """
    Build a team-level analysis dict for the coach view.

    Returns:
    {
        "team_stats":      [{player_id, distance_m, top_speed_kmh, sprints, passes, pass_pct, zone_att_pct}, ...],
        "summary":         [str, str, str],
        "recommendations": [{drill, duration, focus}, ...],
        "ai_generated":    bool,
    }
    """
    per_player  = result_dict.get("per_player_metrics", []) or []
    pass_stats  = result_dict.get("pass_stats",  {}) or {}
    event_metrics = result_dict.get("event_metrics", {}) or {}
    fps         = float(result_dict.get("fps", 25.0))

    # ── Build per-player summary rows ─────────────────────────────────────────
    team_stats = []
    for idx, p in enumerate(per_player):
        zone_frames = p.get("zone_frames", {})
        za = zone_frames.get("attacking_third", 0)
        zt = max(sum(zone_frames.values()), 1)
        ps = (p.get("pass_stats") or {}) if isinstance(p.get("pass_stats"), dict) else {}
        # fallback: team pass_stats split equally if per-player not available
        p_passes   = int(ps.get("total",    pass_stats.get("total",    0)))
        p_accurate = int(ps.get("accurate", 0))
        p_pct      = float(ps.get("accuracy_pct", pass_stats.get("accuracy_pct", 0.0)))
        team_stats.append({
            "player_id":    p.get("player_id", idx),
            "distance_m":   float(p.get("distance_m",    0.0)),
            "top_speed_kmh": float(p.get("max_speed_mps", 0.0)) * 3.6,
            "sprints":       int(p.get("sprint_count",   0)),
            "passes":        p_passes,
            "pass_accuracy_pct": p_pct,
            "zone_att_pct":  round(za / zt * 100, 1),
        })

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            summary, recs = _call_claude_coach(team_stats, pass_stats, event_metrics, fps)
            return {
                "team_stats":      team_stats,
                "summary":         summary,
                "recommendations": recs,
                "ai_generated":    True,
            }
        except Exception as exc:
            log.warning("Claude coach API call failed — using rule-based fallback: %s", exc)

    summary, recs = _rule_based_coach(team_stats, pass_stats, event_metrics)
    return {
        "team_stats":      team_stats,
        "summary":         summary,
        "recommendations": recs,
        "ai_generated":    False,
    }


def _call_claude_coach(
    team_stats: List[Dict],
    pass_stats: Dict,
    event_metrics: Dict,
    fps: float,
) -> Tuple[List[str], List[Dict]]:
    import anthropic

    if not team_stats:
        raise ValueError("No player data")

    n_players   = len(team_stats)
    top_runner  = max(team_stats, key=lambda p: p["distance_m"])
    top_speed_p = max(team_stats, key=lambda p: p["top_speed_kmh"])
    total_dist  = sum(p["distance_m"] for p in team_stats)
    avg_att_pct = sum(p["zone_att_pct"] for p in team_stats) / n_players
    total_sprints = sum(p["sprints"] for p in team_stats)
    total_shots = int(event_metrics.get("shot_count", 0))
    total_passes = int(pass_stats.get("total", 0))
    team_pass_pct = float(pass_stats.get("accuracy_pct", 0.0))

    rows = "\n".join(
        f"  P{p['player_id']}: dist={p['distance_m']:.0f}m  "
        f"top={p['top_speed_kmh']:.1f}km/h  sprints={p['sprints']}  "
        f"att_zone={p['zone_att_pct']:.0f}%"
        for p in team_stats
    )

    stats_text = f"""Players tracked: {n_players}
Total team distance: {total_dist / 1000:.2f} km
Team pass accuracy: {team_pass_pct:.0f}%  ({total_passes} passes total)
Total sprints across team: {total_sprints}
Total shots: {total_shots}
Avg time in attacking third: {avg_att_pct:.0f}%
Top runner: Player {top_runner['player_id']} ({top_runner['distance_m']:.0f} m)
Fastest player: Player {top_speed_p['player_id']} ({top_speed_p['top_speed_kmh']:.1f} km/h)

Per-player breakdown:
{rows}"""

    schema = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Exactly 3 sentences — coach perspective: "
                    "[1] overall team work-rate and distance, "
                    "[2] attacking threat / best individual contributor, "
                    "[3] main tactical weakness to address in training"
                ),
            },
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name":             {"type": "string",  "description": "Short team drill name"},
                        "duration_minutes": {"type": "integer", "description": "Duration in minutes"},
                        "goal":             {"type": "string",  "description": "One sentence: which team weakness this targets"},
                        "instructions":     {"type": "string",  "description": "2-3 sentences on how to run the drill with a full squad"},
                        "difficulty":       {"type": "string",  "enum": ["easy", "medium", "hard"]},
                    },
                    "required": ["name", "duration_minutes", "goal", "instructions", "difficulty"],
                    "additionalProperties": False,
                },
                "description": (
                    "3 to 5 team training drills that directly address the squad weaknesses "
                    "identified in the stats. Each must be runnable on a full training pitch."
                ),
            },
        },
        "required": ["summary", "recommendations"],
        "additionalProperties": False,
    }

    client = anthropic.Anthropic(timeout=25.0)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=1800,
        system=(
            "You are a professional football head coach and performance analyst. "
            "Write to the coach ('Your team…', 'The squad…'). "
            "Be specific — reference the real numbers given. "
            "Be constructive and tactical. Keep each sentence to 1-2 lines. "
            "Respond with valid JSON only — no prose, no markdown fences."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Analyse this team session:\n\n{stats_text}\n\n"
                "Return this JSON (summary: exactly 3 strings, "
                "recommendations: 3–5 team drills with name/duration_minutes/goal/instructions/difficulty)."
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
    recs    = data.get("recommendations", [])[:5]

    _FALLBACK_TEAM_DRILL = {
        "name": "Team fitness circuit",
        "duration_minutes": 20,
        "goal": "Maintain squad conditioning and group cohesion.",
        "instructions": (
            "Divide the squad into groups of 4. "
            "Each group cycles through: shuttle runs, passing squares, and defensive slide drills. "
            "Rotate every 5 minutes."
        ),
        "difficulty": "medium",
    }
    while len(summary) < 3:
        summary.append("Team analysis unavailable.")
    while len(recs) < 3:
        recs.append(_FALLBACK_TEAM_DRILL)

    return summary, recs


def _rule_based_coach(
    team_stats: List[Dict],
    pass_stats: Dict,
    event_metrics: Dict,
) -> Tuple[List[str], List[Dict]]:
    if not team_stats:
        return (
            ["No player data available.", "—", "—"],
            [{"drill": "Team fitness circuit", "duration": "20 minutes", "focus": "Conditioning"}],
        )

    n_players   = len(team_stats)
    total_dist  = sum(p["distance_m"] for p in team_stats)
    avg_dist    = total_dist / n_players
    top_runner  = max(team_stats, key=lambda p: p["distance_m"])
    avg_att_pct = sum(p["zone_att_pct"] for p in team_stats) / n_players
    total_sprints = sum(p["sprints"] for p in team_stats)
    team_pass_pct = float(pass_stats.get("accuracy_pct", 0.0))
    total_shots = int(event_metrics.get("shot_count", 0))

    # Sentence 1: overall work rate
    s1 = (
        f"The squad covered a combined {total_dist / 1000:.2f} km — "
        f"an average of {avg_dist / 1000:.2f} km per tracked player, "
        f"with {total_sprints} sprint bursts across the team."
    )

    # Sentence 2: best contributor / attacking presence
    if top_runner["distance_m"] > avg_dist * 1.3:
        s2 = (
            f"Player {top_runner['player_id']} led the team with "
            f"{top_runner['distance_m']:.0f} m covered — a standout engine in midfield."
        )
    elif avg_att_pct >= 35:
        s2 = (
            f"The team showed good attacking intent, spending an average of "
            f"{avg_att_pct:.0f}% of time in the opposition's third. "
            f"Total shots recorded: {total_shots}."
        )
    else:
        s2 = (
            f"With {total_shots} shots and {avg_att_pct:.0f}% average time in the "
            f"attacking third, there is room to push higher up the pitch."
        )

    # Sentence 3: main weakness
    weaknesses = []
    if team_pass_pct < 65 and team_pass_pct > 0:
        weaknesses.append(
            f"Team passing accuracy was {team_pass_pct:.0f}% — "
            "work on quick combination play under pressure in training."
        )
    if avg_att_pct < 25:
        weaknesses.append(
            "The team spent too little time in the final third; "
            "focus on faster transitions and forward runs from midfield."
        )
    if total_sprints / max(n_players, 1) < 2:
        weaknesses.append(
            "Sprint output per player was low — "
            "add high-intensity intervals to sharpen explosive movement."
        )
    s3 = weaknesses[0] if weaknesses else (
        "Focus on maintaining this intensity over a full 90 minutes — "
        "late-game endurance and pressing triggers are the next priorities."
    )

    summary = [s1, s2, s3]

    # Drills
    drills: List[Dict] = []
    if team_pass_pct < 70 and team_pass_pct > 0:
        drills.append({
            "name": "Positional rondo (8v4)",
            "duration_minutes": 20,
            "goal": "Raise team passing accuracy and sharpen collective pressing triggers.",
            "instructions": (
                "8 outfield players keep possession inside a 20 × 20 m grid against 4 defenders. "
                "Limit to two touches. When defenders win the ball the last two players who lost it swap in. "
                "Coach calls 'press' to trigger coordinated pressing from defenders."
            ),
            "difficulty": "medium",
        })
    if avg_att_pct < 30:
        drills.append({
            "name": "Transition attack (3v2 into full goal)",
            "duration_minutes": 20,
            "goal": "Speed up transitions from defence to attack and increase time in the final third.",
            "instructions": (
                "Start with 3 attackers vs 2 defenders from the halfway line. "
                "Attackers must finish within 8 seconds. "
                "On every turnover, 2 new defenders sprint out while attackers reset. "
                "Run 12 reps, tracking shot conversion."
            ),
            "difficulty": "hard",
        })
    if total_sprints / max(n_players, 1) < 3:
        drills.append({
            "name": "Team sprint ladder (6 × 60 m)",
            "duration_minutes": 15,
            "goal": "Lift collective sprint capacity and explosive acceleration across the squad.",
            "instructions": (
                "Line the full squad on the goal line. "
                "Sprint 60 m on whistle, jog back as recovery (90 s). "
                "Complete 6 rounds. Track last-place finisher each set — "
                "team must beat their previous best on the final rep."
            ),
            "difficulty": "hard",
        })

    generic = [
        {
            "name": "11v11 structured possession shape",
            "duration_minutes": 25,
            "goal": "Reinforce defensive compactness and controlled build-up under pressure.",
            "instructions": (
                "Set up in your match formation. Possession team tries to move through all thirds. "
                "Defending team holds their shape; coach pauses play to correct positioning. "
                "Alternate possession every 5 minutes."
            ),
            "difficulty": "medium",
        },
        {
            "name": "Cross and finish from wide areas",
            "duration_minutes": 20,
            "goal": "Increase shot volume and attacking threat from wide positions.",
            "instructions": (
                "Wingers serve crosses from the byline and cut-back position alternately. "
                "2 strikers and 1 late midfielder arrive into the box on each cross. "
                "Rotate crossers every 3 minutes. Target: 70% of crosses converted to shots."
            ),
            "difficulty": "medium",
        },
        {
            "name": "Set-piece preparation block",
            "duration_minutes": 15,
            "goal": "Convert more attacking corners and free-kicks while defending set-pieces better.",
            "instructions": (
                "Split into attacking and defending groups. "
                "Work through 3 attacking corner routines and 2 near-post free-kick routines. "
                "Each routine repeated 4 times. Swap groups and repeat."
            ),
            "difficulty": "easy",
        },
    ]
    for g in generic:
        if len(drills) >= 5:
            break
        drills.append(g)

    return summary, drills[:5]


# ── Player style archetype ────────────────────────────────────────────────────

def _compute_player_style(
    player: Dict,
    pass_stats: Dict,
    rating: Dict,
    manual_stats: Optional[Dict] = None,
) -> Dict:
    """
    Derive a football movement archetype from aggregated stats.
    Returns {archetype, description, traits}.
    """
    zone_frames = player.get("zone_frames", {})
    zd = zone_frames.get("defensive_third", 0)
    zm = zone_frames.get("middle_third",    0)
    za = zone_frames.get("attacking_third", 0)
    zt = max(zd + zm + za, 1)
    def_pct = zd / zt * 100
    mid_pct = zm / zt * 100
    att_pct = za / zt * 100

    sprint_count = int(player.get("sprint_count", 0))
    avg_spd      = float(player.get("avg_speed_mps", 0.0))

    ms = manual_stats or {}
    manual_total = int(ms.get("passes_made", 0))
    manual_acc   = int(ms.get("passes_successful", 0))
    if manual_total > 0:
        pass_pct = manual_acc / manual_total * 100
        has_pass = True
    else:
        pass_total = int(pass_stats.get("total", 0))
        pass_acc   = int(pass_stats.get("accurate", 0))
        pass_pct   = float(pass_stats.get("accuracy_pct", 0.0))
        has_pass   = pass_total >= 3

    aerials = int(ms.get("aerial_duels_total", 0))

    if att_pct >= 40 and sprint_count >= 4:
        archetype    = "Winger / Wide Forward"
        description  = ("Your explosive runs and high time in the attacking third "
                        "mark you as a dangerous wide threat who stretches defences.")
        traits       = ["Explosive acceleration", "Attacks wide channels", "Direct, fast-break style"]

    elif att_pct >= 35 and sprint_count < 4:
        archetype    = "Advanced Forward"
        description  = ("Your positioning in the final third shows a striker's "
                        "instinct — you find space where it matters most.")
        traits       = ["Strong goal-area presence", "Clinical positioning", "Arrives late into danger areas"]

    elif def_pct >= 45 and has_pass and pass_pct >= 70:
        archetype    = "Deep-Lying Playmaker"
        description  = ("High defensive presence combined with accurate distribution "
                        "marks you as the player who dictates tempo from deep.")
        traits       = ["Ball retention under pressure", "Builds from the back", "High passing accuracy"]

    elif aerials >= 3:
        archetype    = "Aerial Threat / Target Man"
        description  = ("Your aerial duel involvement suggests a physically dominant "
                        "presence — a genuine target for long balls and set pieces.")
        traits       = ["Wins aerial duels", "Holds up play", "Set-piece danger"]

    elif def_pct >= 45:
        archetype    = "Defensive Midfielder / Centre-Back"
        description  = ("Your dominant time in the defensive third shows a disciplined, "
                        "defensive-minded player who protects the backline.")
        traits       = ["Reads danger early", "Wins the ball back", "Screens the defence"]

    elif mid_pct >= 45 and sprint_count >= 3:
        archetype    = "Box-to-Box Midfielder"
        description  = ("Your balanced zone coverage and sprint capacity are the hallmarks "
                        "of a complete midfielder who contributes in all phases.")
        traits       = ["High stamina", "Contributes offensively and defensively", "Covers every blade of grass"]

    elif mid_pct >= 45 and has_pass and pass_pct >= 68:
        archetype    = "Central Midfielder / Playmaker"
        description  = ("Your midfield dominance and tidy passing show a player who "
                        "controls tempo and connects defence to attack.")
        traits       = ["Dictates the tempo", "Clean ball distribution", "High football IQ"]

    elif avg_spd >= 2.5 and sprint_count >= 3:
        archetype    = "High-Press Forward"
        description  = ("Your relentless movement and sprint capacity suggest a tireless "
                        "pressing machine who forces mistakes high up the pitch.")
        traits       = ["Constant pressing", "High work rate", "Forces errors in build-up"]

    else:
        archetype    = "Dynamic All-Rounder"
        description  = ("Your balanced contribution across all zones shows a versatile "
                        "player who adapts to the team's tactical needs.")
        traits       = ["Versatile and adaptable", "Covers all areas", "Consistent work rate"]

    return {"archetype": archetype, "description": description, "traits": traits}
