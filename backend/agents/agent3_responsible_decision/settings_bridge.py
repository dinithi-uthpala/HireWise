"""Read Agent 3 thresholds from the project settings (config.py / .env).

extraction_confidence_ok and borderline_margin are not fields of Settings, so
they are read from the environment or the .env file directly.
"""
from __future__ import annotations

import os

from dotenv import dotenv_values

from backend.config import ROOT_DIR, get_settings
from backend.schemas import ReviewThresholds


def _extra(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        raw = dotenv_values(ROOT_DIR / ".env").get(name)
    try:
        return float(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def thresholds_from_settings() -> ReviewThresholds:
    s = get_settings()
    return ReviewThresholds(
        extraction_confidence_ok=getattr(s, "extraction_confidence_ok",
                                         _extra("EXTRACTION_CONFIDENCE_OK", 0.75)),
        matching_confidence_ok=s.matching_confidence_ok,
        strong_match_min=s.strong_match_min,
        potential_match_min=s.potential_match_min,
        borderline_margin=getattr(s, "borderline_margin", _extra("BORDERLINE_MARGIN", 2.0)),
    )
