"""Extraction-confidence scoring (Agent 1).

Produces the 0..1 confidence value shown in the dashboard and used by
Agent 3's human-review rules. A low score means "some sections of the CV
could not be reliably extracted" - never a silent guess.

Signal mix (deterministic, auditable):
    + text volume          (enough content to parse?)
    + sections found       (skills / education / experience)
    + structured richness  (certs, projects, summary)
    - thin documents       (very short text)
    - no experience dates  (cannot compute relevant experience)
"""
from __future__ import annotations

from backend.schemas import CandidateProfile

_MIN_TEXT = 30          # below this the document is unreadable
_THIN_TEXT = 200        # below this the CV is considered "thin"


def is_unreadable(text: str) -> bool:
    """True when extraction produced (almost) no text - e.g. a scanned PDF."""
    return len(text.strip()) < _MIN_TEXT


def compute_confidence(text: str, profile: CandidateProfile) -> float:
    """Score how reliably the CV was parsed, in the inclusive range 0..1."""
    score = 0.45  # neutral baseline

    # 1. text volume
    n = len(text.strip())
    if n >= 800:
        score += 0.12
    elif n >= 400:
        score += 0.08
    elif n >= _THIN_TEXT:
        score += 0.04
    else:
        score -= 0.20

    # 2. key structured content
    if profile.technical_skills:
        score += 0.10
    if profile.education:
        score += 0.08
    if profile.experience_entries:
        score += 0.08
    else:
        score -= 0.05  # no usable dates -> relevant experience unknown
    if profile.certifications or profile.projects:
        score += 0.04
    if profile.summary:
        score += 0.04

    # 3. clamp into [0, 1]
    return round(max(0.0, min(1.0, score)), 2)


def parse_status_for(confidence: float, text: str, threshold: float) -> str:
    """Map confidence + readability to the parse status reported to Agent 3."""
    if is_unreadable(text):
        return "failed"
    if confidence < threshold:
        return "low_confidence"
    return "ok"


def warnings_for(text: str, profile: CandidateProfile, pii_found: bool) -> list[str]:
    """Human-readable warnings attached to the extraction result."""
    warnings: list[str] = []
    if is_unreadable(text):
        warnings.append(
            "Document contains almost no extractable text (possible scanned/image PDF)."
        )
        return warnings
    if len(text.strip()) < _THIN_TEXT:
        warnings.append("CV text is very short; extraction may be incomplete.")
    if not profile.experience_entries:
        warnings.append("No work-experience date ranges found; total experience is uncertain.")
    if not profile.technical_skills:
        warnings.append("No technical skills detected against the skill taxonomy.")
    if not profile.education:
        warnings.append("No education entries detected.")
    if not pii_found:
        warnings.append("No personal identifiers detected; verify the document is a CV.")
    return warnings