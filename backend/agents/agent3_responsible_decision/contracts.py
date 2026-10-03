"""Request/response models for the Agent 3 REST API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.schemas import ExtractionResult, MatchResult, ReviewOutput


class ReviewRequest(BaseModel):
    """Input of POST /api/agent3/review: what Agents 1 and 2 produced."""

    extraction: ExtractionResult
    match: MatchResult


class HumanDecisionIn(BaseModel):
    decision: Literal["shortlist", "hold", "not_selected"]
    note: str = Field(default="", max_length=2000)


class HumanDecisionOut(BaseModel):
    candidate_id: str
    job_id: str = ""
    decision: str
    note: str = ""
    decided_by: str = ""
    ai_recommendation_code: str = ""
    is_override: bool = False
    ts: str = ""


class CandidateSummary(BaseModel):
    candidate_id: str
    job_id: str
    match_score: float | None = None
    recommendation_code: str
    recommendation: str
    extraction_confidence: float = 0.0
    risk_flag_codes: list[str] = Field(default_factory=list)
    status: str = "awaiting_human_review"
    final_decision: str = ""
    # Notes that only make sense when candidates are compared (ties, odd patterns)
    batch_notes: list[str] = Field(default_factory=list)


class CandidateDetail(BaseModel):
    summary: CandidateSummary
    extraction: ExtractionResult
    match: MatchResult
    review: ReviewOutput
    decisions: list[HumanDecisionOut] = Field(default_factory=list)


class AuditEventOut(BaseModel):
    id: int
    candidate_id: str
    actor: str
    action: str
    summary: dict[str, Any] = Field(default_factory=dict)
    ts: str
    entry_hash: str


class AuditVerifyOut(BaseModel):
    valid: bool
    entries_checked: int
    first_bad_entry_id: int | None = None


class FairnessRequest(BaseModel):
    cv_a_label: str
    cv_b_label: str
    review_a: ReviewOutput
    review_b: ReviewOutput
    tolerance: float = Field(default=0.5, ge=0)


class FairnessTestResult(BaseModel):
    cv_a_label: str
    cv_b_label: str
    score_a: float | None = None
    score_b: float | None = None
    difference: float | None = None
    tolerance: float = 0.5
    same_recommendation: bool = False
    passed: bool = False
    explanation: str = ""
