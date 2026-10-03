"""Agent 3 - Responsible Decision Agent (entry point).

review_candidate(extraction, match) is the ONLY function other code needs:

    Agent 1 ExtractionResult --+
                               +--> review_candidate() --> ReviewOutput
    Agent 2 MatchResult -------+

It never makes a hiring decision: ReviewOutput.human_review_required is
typed Literal[True], so a review that skips the human cannot even be built.
"""
from __future__ import annotations

from backend.schemas import ExtractionResult, MatchResult, ReviewOutput, ReviewThresholds

from .explain import build_explanation
from .rules import (
    build_flags,
    check_privacy,
    choose_recommendation,
    derive_matching_confidence,
)


def review_candidate(
    extraction: ExtractionResult,
    match: MatchResult,
    thresholds: ReviewThresholds | None = None,
) -> ReviewOutput:
    th = thresholds or ReviewThresholds()

    privacy = check_privacy(extraction, match)
    matching_conf = derive_matching_confidence(match)
    flags = build_flags(extraction, match, privacy, matching_conf, th)
    code, label = choose_recommendation(match.match_score, flags, th)
    explanation = build_explanation(extraction, match, label, flags, privacy, matching_conf)

    return ReviewOutput(
        candidate_id=match.candidate_id,
        job_id=match.job_id,
        match_score=match.match_score,
        extraction_confidence=extraction.extraction_confidence,
        matching_confidence=matching_conf,
        recommendation_code=code,
        recommendation=label,
        explanation=explanation,
        risk_flags=flags,
        privacy_check=privacy,
    )
