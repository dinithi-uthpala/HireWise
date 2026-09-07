"""Pydantic schemas: the typed JSON contract exchanged between the
three HireWise agents (REST + JSON agent-communication protocol).

These schemas are validated with Pydantic on every hop, which keeps the
agent outputs clean, predictable and safe (assignment requirement).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Security / auth
# ---------------------------------------------------------------------------
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    full_name: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    full_name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=160)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="Recruiter")   # Recruiter | HR Admin | Viewer


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Agent 1 - Candidate Intelligence Agent
# ---------------------------------------------------------------------------
class ExperienceEntry(BaseModel):
    role: str = ""
    employer: str = ""
    start: str = ""
    end: str = ""
    months: float = 0.0
    summary: str = ""


class EducationEntry(BaseModel):
    degree: str = ""
    qualification_level: str = ""          # Bachelor | Master | Diploma | ...
    subject: str = ""
    # NOTE: institution is captured but RESTRICTED from scoring.
    institution: str = ""


class PIIItem(BaseModel):
    type: str                              # name |email|phone|address|national_id|dob|gender|religion|ethnicity|marital|disability|photo|signature|...
    detected: str = ""                     # short safe preview of the removed value (masked)
    action: str = "redacted"               # redacted | removed | kept_reference_only


class PIIReport(BaseModel):
    detected_count: int = 0
    items: list[PIIItem] = Field(default_factory=list)
    redacted_text: str = ""                 # CV text after redaction (no raw PII)


class CandidateProfile(BaseModel):
    """Anonymous, job-relevant profile sent from Agent 1 to Agent 2."""
    candidate_id: str
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    employers: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    experience_entries: list[ExperienceEntry] = Field(default_factory=list)
    total_experience_years: float = 0.0
    summary: str = ""


class ExtractionResult(BaseModel):
    """Agent 1 --> output payload."""
# ---------------------------------------------------------------------------
# Agent 2 - Job Matching & Retrieval Agent
# ---------------------------------------------------------------------------
class JobRequirements(BaseModel):
    """Requirements extracted from a vacancy description + rubric retrieval."""
    job_id: int | None = None
    title: str
    mandatory_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_years: float = 0.0
    essential_qualifications: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)
    retrieval_confidence: float = Field(default=0.0, ge=0, le=1)


class RetrievedDocument(BaseModel):
    id: str = ""
    title: str = ""
    content_preview: str = ""
    score: float = Field(default=0.0, ge=0, le=1)


class SkillMatch(BaseModel):
    skill: str
    required: str = "mandatory"           # mandatory | preferred
    matched: bool
    method: str = "exact"                 # exact | synonym | taxonomy | semantic | absent
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    candidate_match_text: str = ""


class SkillGap(BaseModel):
    covered: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    coverage_ratio: float = Field(default=0.0, ge=0, le=1)


class ComponentScore(BaseModel):
    mandatory_skills: float = Field(default=0.0, ge=0, le=100)
    experience: float = Field(default=0.0, ge=0, le=100)
    education: float = Field(default=0.0, ge=0, le=100)
    preferred_skills: float = Field(default=0.0, ge=0, le=100)
    component_contributions: dict[str, float] = Field(default_factory=dict)   # weighted pts


class MatchResultData(BaseModel):
    """Agent 2 --> output payload (full evidence-backed result)."""
    job_id: int | None = None
    candidate_id: str
    total_score: float = Field(default=0.0, ge=0, le=100)
    components: ComponentScore = Field(default_factory=ComponentScore)
    requirements: JobRequirements = Field(default_factory=lambda: JobRequirements(title=""))
    skill_matches: list[SkillMatch] = Field(default_factory=list)
    skill_gap: SkillGap = Field(default_factory=SkillGap)
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    rubric_weights: dict[str, float] = Field(default_factory=dict)
    explanation_parts: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent 3 - Responsible Decision Agent
# ---------------------------------------------------------------------------
class PrivacyCheck(BaseModel):
    passed: bool = True
    sensitive_fields_used: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)


class ReviewRuleResult(BaseModel):
    rule: str
    triggered: bool
    message: str = ""


class ReviewOutput(BaseModel):
    """Agent 3 --> output payload."""
    candidate_id: str
    recommendation: str = "Manual Review"   # Strong Match | Potential Match | Manual Review | Not Recommended
    explanation: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    privacy_check: PrivacyCheck = Field(default_factory=PrivacyCheck)
    extraction_confidence: float = 0.0
    matching_confidence: float = 0.0
    human_review_required: bool = False
    human_review_rules: list[ReviewRuleResult] = Field(default_factory=list)
    decision_support_statement: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FairnessTestResult(BaseModel):
    pair: list[str] = Field(default_factory=list)
    scores_before: dict[str, float] = Field(default_factory=dict)
    scores_after: dict[str, float] = Field(default_factory=dict)
    passed: bool = True
    message: str = ""


class HumanDecisionIn(BaseModel):
    decision: str = Field(pattern="^(shortlist|hold|not_selected)$")
    notes: str = ""
    is_override: bool = False


# ---------------------------------------------------------------------------
# Generic envelope helpers
# ---------------------------------------------------------------------------
class Message(BaseModel):
    status: str = "ok"
    detail: str = ""


class AgentActivityOut(BaseModel):
    agent: str = ""
    action: str = ""
    status: str = "ok"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    candidate_id: str
    profile: CandidateProfile
    pii: PIIReport
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    parse_status: str = "ok"               # ok | low_confidence | failed
    warnings: list[str] = Field(default_factory=list)
    source_hash: str = ""