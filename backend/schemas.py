"""Pydantic schemas = the typed JSON contract exchanged between agents.

These schemas define the agent-communication protocol over REST + JSON and
are validated on every hop, which keeps the agent outputs clean, predictable
and safe.

Contains the Agent 1 and Agent 2 communication contracts. Agent 3 models can
be added here as that agent is implemented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


# ===========================================================================
# Agent 1 - Candidate Intelligence Agent
# ===========================================================================
class ExperienceEntry(BaseModel):
    """One work-experience record extracted from a CV."""

    role: str = ""
    employer: str = ""
    start: str = ""                # human readable, e.g. "Jan 2021"
    end: str = ""                  # human readable, "Present" possible
    months: float = Field(default=0.0, ge=0)   # duration in months
    summary: str = ""


class EducationEntry(BaseModel):
    """One education record. NOTE: `institution` is captured but restricted
    from scoring (Responsible AI decision: avoid university bias)."""

    degree: str = ""
    qualification_level: str = ""   # PhD | Master | Bachelor | Diploma | ...
    subject: str = ""
    institution: str = ""


class PIIItem(BaseModel):
    """A single personally-identifiable-information detection."""

    type: str                        # name|email|phone|nic|passport|address|dob|age|gender|religion|ethnicity|marital_status|disability|nationality|university|other
    detected: str = ""               # masked preview of the removed value
    action: str = "redacted"         # redacted | removed | kept_reference_only


class PIIReport(BaseModel):
    """Agent 1 privacy report: what was detected and removed."""

    detected_count: int = 0
    items: list[PIIItem] = Field(default_factory=list)
    redacted_text: str = ""          # CV text after redaction (no raw PII)


class CandidateProfile(BaseModel):
    """Anonymous, job-relevant profile sent from Agent 1 to Agent 2.

    This object must never contain full name, email, phone, NIC, address,
    gender, date of birth, religion, ethnicity, marital status etc.
    """

    candidate_id: str
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    employers: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    experience_entries: list[ExperienceEntry] = Field(default_factory=list)
    total_experience_years: float = Field(default=0.0, ge=0)
    summary: str = ""


class ExtractionResult(BaseModel):
    """Agent 1 --> output payload (the complete result of processing one CV)."""

    candidate_id: str
    profile: CandidateProfile
    pii: PIIReport
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    parse_status: str = "ok"         # ok | low_confidence | failed
    extraction_method: str = "deterministic"   # deterministic | llm_enhanced
    warnings: list[str] = Field(default_factory=list)
    source_hash: str = ""            # sha256 of the original upload
    stored_cv_path: str = ""         # path of the encrypted original CV


# ===========================================================================
# Agent 2 - Job Matching & Retrieval Agent
# ===========================================================================
class JobRequirement(BaseModel):
    """Sanitized, normalized requirements for one job vacancy."""

    job_id: str = ""
    title: str = ""
    description: str = ""
    mandatory_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_experience_years: float = Field(default=0.0, ge=0)
    required_education_level: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    required_certifications: list[str] = Field(default_factory=list)


class JobCreate(BaseModel):
    """JSON payload for creating one persisted vacancy."""

    job_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$",
    )
    job_title: str = Field(min_length=1, max_length=200)
    job_description: str = Field(min_length=1, max_length=100_000)


class JobOut(BaseModel):
    """Persisted vacancy returned by the Agent 2 job API."""

    job_id: str
    job_title: str
    job_description: str
    created_at: datetime


class ScoreBreakdown(BaseModel):
    """Weighted Agent 2 component contributions to the 0-100 final score."""

    mandatory_skills: float = Field(default=0.0, ge=0, le=100)
    experience: float = Field(default=0.0, ge=0, le=100)
    education: float = Field(default=0.0, ge=0, le=100)
    preferred_skills: float = Field(default=0.0, ge=0, le=100)


class SkillGap(BaseModel):
    """A required or preferred skill missing from the candidate profile."""

    skill: str
    category: Literal["mandatory", "preferred"]
    reason: str = ""


class RetrievalEvidence(BaseModel):
    """Compact source reference returned by Agent 2 retrieval."""

    source: str
    category: str = ""
    relevance: float | None = Field(default=None, ge=0, le=1)
    related_skills: list[str] = Field(default_factory=list)


class RequirementMatchEvidence(BaseModel):
    """Deterministic, non-scoring evidence for additional requirements."""

    required: list[str] = Field(default_factory=list)
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    evidence: str = ""


class UncertainMatch(BaseModel):
    """A requirement where candidate evidence is present but inconclusive."""

    requirement_type: Literal[
        "skill", "experience", "education", "certification", "responsibility"
    ]
    requirement: str
    reason: str
    candidate_evidence: str = ""


class SkillScoreEvidence(BaseModel):
    """Explainable evidence for a mandatory or preferred skill component."""

    score: float = Field(default=0.0, ge=0, le=100)
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    related_matches: dict[str, list[str]] = Field(default_factory=dict)
    evidence: str = ""


class ExperienceScoreEvidence(BaseModel):
    """Explainable evidence for the experience component."""

    score: float = Field(default=0.0, ge=0, le=100)
    candidate_years: float = Field(default=0.0, ge=0)
    required_years: float = Field(default=0.0, ge=0)
    evidence: str = ""


class EducationScoreEvidence(BaseModel):
    """Explainable evidence for the combined education/certification component."""

    score: float = Field(default=0.0, ge=0, le=15)
    candidate_education: list[str] = Field(default_factory=list)
    required_education: str = ""
    education_match_status: Literal["matched", "partial", "missing", "uncertain", "not_required"] = "not_required"
    education_contribution: float = Field(default=0.0, ge=0, le=15)
    required_certifications: list[str] = Field(default_factory=list)
    matched_certifications: list[str] = Field(default_factory=list)
    missing_certifications: list[str] = Field(default_factory=list)
    certification_match_status: Literal["matched", "partial", "missing", "not_required"] = "not_required"
    certification_contribution: float = Field(default=0.0, ge=0, le=15)
    total_combined_contribution: float = Field(default=0.0, ge=0, le=15)
    evidence: str = ""


class ScoreEvidence(BaseModel):
    """Component-level explanations for the deterministic score."""

    mandatory_skills: SkillScoreEvidence = Field(default_factory=SkillScoreEvidence)
    preferred_skills: SkillScoreEvidence = Field(default_factory=SkillScoreEvidence)
    experience: ExperienceScoreEvidence = Field(default_factory=ExperienceScoreEvidence)
    education: EducationScoreEvidence = Field(default_factory=EducationScoreEvidence)


class MatchResult(BaseModel):
    """Agent 2 result for one candidate and one job."""

    candidate_id: str
    job_id: str = ""
    parse_status: Literal["ok", "low_confidence", "failed"] = "ok"
    match_status: Literal["scored", "warning", "unavailable"] = "scored"
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    match_score: float | None = Field(default=None, ge=0, le=100)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    matched_mandatory_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[SkillGap] = Field(default_factory=list)
    retrieval_evidence: list[RetrievalEvidence] = Field(default_factory=list)
    score_evidence: ScoreEvidence = Field(default_factory=ScoreEvidence)
    responsibility_evidence: RequirementMatchEvidence = Field(
        default_factory=RequirementMatchEvidence
    )
    certification_evidence: RequirementMatchEvidence = Field(
        default_factory=RequirementMatchEvidence
    )
    uncertain_matches: list[UncertainMatch] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ===========================================================================
# Generic helpers shared by the API layer
# ===========================================================================
class Message(BaseModel):
    status: str = "ok"
    detail: str = ""


class AgentActivityOut(BaseModel):
    agent: str = ""
    action: str = ""
    status: str = "ok"               # running | ok | warning | error
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


    # ===========================================================================
# Agent 3 - Responsible Decision Agent   (PASTE AT THE VERY BOTTOM of schemas.py)
# Uses only names that schemas.py already imports:
#   BaseModel, Field, Literal, datetime, timezone
# ===========================================================================
class RiskFlag(BaseModel):
    """One issue the recruiter should know about."""

    code: str                                   # e.g. "LOW_EXTRACTION_CONFIDENCE"
    severity: Literal["info", "warning", "critical"] = "warning"
    message: str                                # plain language, no personal data
    forces_manual_review: bool = False          # True => label becomes MANUAL_REVIEW


class ReviewThresholds(BaseModel):
    """HR-configurable limits. Defaults follow the HireWise design document."""

    extraction_confidence_ok: float = Field(default=0.75, ge=0, le=1)
    matching_confidence_ok: float = Field(default=0.55, ge=0, le=1)
    strong_match_min: float = Field(default=80.0, ge=0, le=100)
    potential_match_min: float = Field(default=60.0, ge=0, le=100)
    borderline_margin: float = Field(default=2.0, ge=0, le=20)


class PrivacyCheck(BaseModel):
    """Result of Agent 3's independent privacy re-check."""

    passed: bool
    checked_items: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)   # never contains raw values


class ReviewOutput(BaseModel):
    """Agent 3 --> output payload. A recommendation, NEVER a hiring decision."""

    candidate_id: str
    job_id: str = ""
    match_score: float | None = Field(default=None, ge=0, le=100)
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    matching_confidence: float = Field(default=0.0, ge=0, le=1)
    recommendation_code: Literal[
        "STRONG_MATCH", "POTENTIAL_MATCH", "INSUFFICIENT_EVIDENCE", "MANUAL_REVIEW"
    ]
    recommendation: str                         # display label shown to the recruiter
    explanation: str
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    privacy_check: PrivacyCheck
    # The AI never decides. Pydantic rejects anything except True.
    human_review_required: Literal[True] = True
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))