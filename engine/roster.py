"""
Matches a user-provided roster (names + team colors) to the internal
team IDs detected by the pipeline, then annotates per_player_metrics
with player names.
"""

from typing import Dict, List, Optional
import numpy as np

# Approximate BGR values for common jersey colours (OpenCV BGR order).
_COLOR_BGR: Dict[str, np.ndarray] = {
    "red":       np.array([50,  50,  200], dtype=np.float32),
    "green":     np.array([50,  160, 50],  dtype=np.float32),
    "blue":      np.array([200, 50,  50],  dtype=np.float32),
    "dark_blue": np.array([140, 20,  20],  dtype=np.float32),
    "white":     np.array([220, 220, 220], dtype=np.float32),
    "black":     np.array([30,  30,  30],  dtype=np.float32),
    "yellow":    np.array([0,   220, 220], dtype=np.float32),
    "orange":    np.array([0,   130, 220], dtype=np.float32),
    "purple":    np.array([150, 30,  150], dtype=np.float32),
    "pink":      np.array([150, 100, 220], dtype=np.float32),
}


def _resolve_team_mapping(
    roster_teams: List[Dict],
    prototypes: Dict[int, np.ndarray],
) -> Dict[str, int]:
    """Map each roster team color name → internal team_id (1 or 2)."""
    if not prototypes or not roster_teams:
        return {}

    used_tids: set = set()
    mapping: Dict[str, int] = {}

    # Sort teams so deterministic when both are equally close
    for team in roster_teams:
        color_name = team.get("color", "").lower().replace(" ", "_")
        ref_bgr = _COLOR_BGR.get(color_name)
        if ref_bgr is None:
            continue

        best_id = min(
            [tid for tid in prototypes if tid not in used_tids] or list(prototypes.keys()),
            key=lambda tid: float(np.linalg.norm(prototypes[tid] - ref_bgr)),
        )
        mapping[color_name] = best_id
        used_tids.add(best_id)

    return mapping


def apply_roster(
    per_player_metrics: List[Dict],
    roster: Optional[Dict],
    prototypes: Dict[int, np.ndarray],
) -> List[Dict]:
    """
    Annotate each player metric dict with a 'name' field.

    Matching strategy:
      1. Resolve roster team color → internal team_id via prototype BGR distance.
      2. Within each team, sort tracks by distance_m descending (most active first).
      3. Assign roster player names in that order.
      4. Unmatched or unnamed tracks fall back to 'Player <track_id>'.
    """
    if not roster:
        for p in per_player_metrics:
            p.setdefault("name", f"Player {p['track_id']}")
        return per_player_metrics

    teams = roster.get("teams", [])
    if not teams:
        for p in per_player_metrics:
            p.setdefault("name", f"Player {p['track_id']}")
        return per_player_metrics

    color_to_tid = _resolve_team_mapping(teams, prototypes)

    # Build {internal_team_id: [ordered names from roster]}
    tid_to_names: Dict[int, List[str]] = {}
    for i, team in enumerate(teams):
        color_name = team.get("color", "").lower().replace(" ", "_")
        tid = color_to_tid.get(color_name, i + 1)
        players = team.get("players", [])
        names = [
            p.get("name", "").strip() or f"#{p.get('jersey', '?')}"
            for p in players
            if p.get("name", "").strip() or p.get("jersey")
        ]
        tid_to_names[tid] = names

    # Group tracks by team
    by_team: Dict[int, List[Dict]] = {}
    unmatched: List[Dict] = []
    for p in per_player_metrics:
        tid = p.get("team_id")
        if tid is not None and tid in tid_to_names:
            by_team.setdefault(tid, []).append(p)
        else:
            unmatched.append(p)

    # Assign names within each team (most active → first listed)
    for tid, players in by_team.items():
        players_sorted = sorted(players, key=lambda x: x["distance_m"], reverse=True)
        names = tid_to_names.get(tid, [])
        for i, p in enumerate(players_sorted):
            if i < len(names):
                p["name"] = names[i]
            else:
                p["name"] = f"Player {p['track_id']}"

    for p in unmatched:
        p.setdefault("name", f"Player {p['track_id']}")

    return per_player_metrics
