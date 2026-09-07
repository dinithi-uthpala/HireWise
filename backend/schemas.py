"""Pydantic schemas = the typed JSON contract exchanged between agents.

These schemas define the agent-communication protocol over REST + JSON and
are validated on every hop, which keeps the agent outputs clean, predictable
and safe.

Currently implemented: Agent 1 (Candidate Intelligence) contract.
Agent 2 / Agent 3 will add their models here as they are built.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

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
    created_at: datetime = Field(default_factory=datetime.utcnow)