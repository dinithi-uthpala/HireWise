"""Read Agent 3 thresholds from the project settings (config.py / .env)."""
from __future__ import annotations

from backend.config import get_settings
from backend.schemas import ReviewThresholds


def thresholds_from_settings() -> ReviewThresholds:
    s = get_settings()
    return ReviewThresholds(
        extraction_confidence_ok=getattr(s, "extraction_confidence_ok", 0.75),
        matching_confidence_ok=s.matching_confidence_ok,
        strong_match_min=s.strong_match_min,
        potential_match_min=s.potential_match_min,
        borderline_margin=getattr(s, "borderline_margin", 2.0),
    )
