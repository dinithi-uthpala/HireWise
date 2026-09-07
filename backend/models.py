"""ORM models (SQLModel / SQLAlchemy 2) for HireWise structured data.

Tables:
    user            HR users + roles (Recruiter, HR Admin, Viewer)
    jobvacancy      job descriptions posted by recruiters
    candidate       one row per uploaded CV (+ encrypted file path + PII report)
    matchresult     Agent 2 output: component scores, evidence, skill gaps
    aireview        Agent 3 output: recommendation, explanation, risk flags
    humandecision   final recruiter decision (shortlist / hold / not-selected)
    auditlog        immutable audit trail
    agentactivity   live agent-communication monitor feed
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlmodel import Field, Relationship, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Identity / roles
# ---------------------------------------------------------------------------
class User(SQLModel, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=40)
    full_name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=160)
    hashed_password: str = Field(max_length=255)
    # Recruiter | HR Admin | Viewer
    role: str = Field(default="Recruiter", max_length=30)
    is_active: bool = True
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Job vacancies
# ---------------------------------------------------------------------------
class JobVacancy(SQLModel, table=True):
    __tablename__ = "jobvacancy"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=160)
    job_description: str = Field(sa_column=Column(Text))
    # Agent 2 requirement analysis (JSON) -- optional, created on demand
    requirements_analysis: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_now)

    candidates: list["Candidate"] = Relationship(back_populates="job")


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------
class Candidate(SQLModel, table=True):
    __tablename__ = "candidate"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="jobvacancy.id", index=True)
    candidate_code: str = Field(index=True)                 # CAND-001
    original_filename: str = Field(default="", max_length=255)
    cv_path: str = Field(default="", max_length=255)        # encrypted file
    cv_sha256: str = Field(default="", max_length=96)
    parse_status: str = Field(default="pending")            # pending|ok|low_confidence|failed
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    # JSON: anonymous candidate profile (Agent 1 output)
    profile_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    # JSON: PII detection / redaction report
# ---------------------------------------------------------------------------
# Agent 2 output
# ---------------------------------------------------------------------------
class MatchResult(SQLModel, table=True):
    __tablename__ = "matchresult"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="jobvacancy.id", index=True)
    candidate_id: Optional[int] = Field(default=None, foreign_key="candidate.id", index=True)
    total_score: float = Field(default=0.0, ge=0, le=100)
    # JSON: component scores, skill matches, evidence, gap analysis,
    #       retrieved KB documents, uncertainties
    detail_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)

    candidate: Optional[Candidate] = Relationship(back_populates="match")


# ---------------------------------------------------------------------------
# Agent 3 output
# ---------------------------------------------------------------------------
class AIRreview(SQLModel, table=True):
    __tablename__ = "aireview"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="jobvacancy.id", index=True)
    candidate_id: Optional[int] = Field(default=None, foreign_key="candidate.id", index=True)
    recommendation: str = Field(default="Manual Review")   # Strong Match | Potential Match | Manual Review | Not Recommended
    explanation: str = Field(default="", sa_column=Column(Text))
    # JSON: risk flags, privacy check results, fairness check, costructure
    review_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)

    candidate: Optional[Candidate] = Relationship(back_populates="review")


# ---------------------------------------------------------------------------
# Human decisions
# ---------------------------------------------------------------------------
class HumanDecision(SQLModel, table=True):
    __tablename__ = "humandecision"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="jobvacancy.id", index=True)
    candidate_id: Optional[int] = Field(default=None, foreign_key="candidate.id", index=True)
    reviewer_id: Optional[int] = Field(default=None, foreign_key="user.id")
    decision: str = Field(max_length=30)            # shortlist | hold | not_selected
    notes: str = Field(default="", sa_column=Column(Text))
    is_override: bool = False                        # human override of AI recommendation
    created_at: datetime = Field(default_factory=_now)

    candidate: Optional[Candidate] = Relationship(back_populates="decision")


# ---------------------------------------------------------------------------
# Audit + monitoring
# ---------------------------------------------------------------------------
class AuditLog(SQLModel, table=True):
    __tablename__ = "auditlog"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, index=True)
    candidate_id: Optional[int] = Field(default=None, index=True)
    actor: str = Field(default="system", max_length=120)   # username or "system"
    event: str = Field(default="", max_length=200)
    detail: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON
    created_at: datetime = Field(default_factory=_now)


class AgentActivity(SQLModel, table=True):
    __tablename__ = "agentactivity"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, index=True)
    candidate_id: Optional[int] = Field(default=None, index=True)
    agent: str = Field(default="", max_length=60)      # intelligence|matching|decision
    action: str = Field(default="", max_length=160)
    status: str = Field(default="running", max_length=20)   # running|ok|warning|error
    payload: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON
    created_at: datetime = Field(default_factory=_now)
    pii_report_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)

    job: Optional[JobVacancy] = Relationship(back_populates="candidates")
    match: Optional["MatchResult"] = Relationship(back_populates="candidate")
    review: Optional["AIRreview"] = Relationship(back_populates="candidate")
    decision: Optional["HumanDecision"] = Relationship(back_populates="candidate")