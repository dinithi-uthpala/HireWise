"""Rules about human decisions (pure logic)."""
from __future__ import annotations

DECISIONS = ("shortlist", "hold", "not_selected")

_POSITIVE_AI = {"STRONG_MATCH", "POTENTIAL_MATCH"}
_NOT_POSITIVE_AI = {"INSUFFICIENT_EVIDENCE", "MANUAL_REVIEW"}


def is_override(ai_code: str, decision: str) -> bool:
    """True when the human disagrees with the AI's direction.

    - shortlisting someone the AI did not back
    - not selecting someone the AI rated Strong/Potential
    'hold' is never an override.
    """
    if decision == "shortlist" and ai_code in _NOT_POSITIVE_AI:
        return True
    if decision == "not_selected" and ai_code in _POSITIVE_AI:
        return True
    return False
