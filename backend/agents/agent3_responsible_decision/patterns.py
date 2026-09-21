"""Cross-candidate checks: tied scores and unusual score patterns.

Design document human-review rules: "Unusual score pattern" and "Tie or
borderline score". Borderline is checked per candidate (rules.py); ties and
patterns need several candidates, so they are computed when a job's candidate
list is shown. These are notes for the recruiter; they never change a label.
"""
from __future__ import annotations


def batch_notes(scores: dict[str, float | None]) -> dict[str, list[str]]:
    """scores: {candidate_id: match_score or None}. Returns notes per candidate."""
    notes: dict[str, list[str]] = {cid: [] for cid in scores}
    scored = {cid: round(s, 1) for cid, s in scores.items() if s is not None}

    groups: dict[float, list[str]] = {}
    for cid, s in scored.items():
        groups.setdefault(s, []).append(cid)

    for s, ids in groups.items():
        if len(ids) >= 2:
            for cid in ids:
                notes[cid].append(
                    f"TIED_SCORE: {len(ids) - 1} other candidate(s) have the same score "
                    f"({s}). Compare them directly."
                )

    if len(scored) >= 3 and len(groups) == 1:
        for cid in scored:
            notes[cid].append(
                f"UNUSUAL_SCORE_PATTERN: all {len(scored)} candidates received the same "
                "score. The rubric may not separate them, so review manually."
            )
    return notes
