"""FastAPI endpoints for the Job Matching & Retrieval Agent."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from backend.agents.agent2_job_matching.agent import match_candidate_to_job
from backend.schemas import CandidateProfile, MatchResult


class MatchRequest(BaseModel):
    """Anonymous Agent 1 profile and job data supplied to Agent 2."""

    candidate: CandidateProfile = Field(
        description="Anonymous CandidateProfile produced by Agent 1."
    )
    job_title: str = Field(
        default="",
        description="The job title, for example 'Junior Data Analyst'.",
        examples=["Junior Data Analyst"],
    )
    job_description: str = Field(
        default="",
        description=(
            "The job requirements. Include recognizable skills and measurable "
            "requirements, for example: Required skills: Python, SQL, Excel. "
            "Preferred skills: Pandas, Power BI. Minimum 1 year of relevant "
            "experience. Bachelor's degree required."
        ),
        examples=[
            "Required skills: Python, SQL, Excel. Preferred skills: Pandas, Power BI. "
            "Minimum 1 year of relevant experience. Bachelor's degree required."
        ],
    )
    parse_status: Literal["ok", "low_confidence", "failed"] = Field(
        default="ok",
        description="Agent 1 extraction status passed to Agent 2.",
        examples=["ok"],
    )
    extraction_confidence: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Agent 1 extraction confidence on a 0 to 1 scale.",
        examples=[0.95],
    )
    job_id: str = Field(
        default="",
        description="Optional job identifier used to correlate the match result.",
        examples=["JOB-001"],
    )


router = APIRouter(prefix="/agent2", tags=["Agent 2 - Job Matching"])


@router.post("/match", response_model=MatchResult)
def match_candidate(
    request: MatchRequest = Body(
        ...,
        openapi_examples={
            "junior_data_analyst": {
                "summary": "Junior Data Analyst matching request",
                "value": {
                    "candidate": {
                        "candidate_id": "CAND-001",
                        "technical_skills": [
                            "Python",
                            "SQL",
                            "Pandas",
                            "Power BI",
                        ],
                        "soft_skills": ["Communication", "Teamwork"],
                        "job_titles": ["Junior Data Analyst"],
                        "employers": [],
                        "education": [
                            {
                                "degree": "Bachelor of Science",
                                "qualification_level": "Bachelor",
                                "subject": "Data Analytics",
                                "institution": "",
                            }
                        ],
                        "certifications": [],
                        "projects": [],
                        "experience_entries": [],
                        "total_experience_years": 1.0,
                        "summary": "Junior Data Analyst with reporting experience.",
                    },
                    "job_title": "Junior Data Analyst",
                    "job_description": (
                        "Required skills: Python, SQL, Excel. "
                        "Preferred skills: Pandas, Power BI. "
                        "Minimum 1 year of relevant experience. "
                        "Bachelor's degree required."
                    ),
                    "parse_status": "ok",
                    "extraction_confidence": 0.95,
                    "job_id": "JOB-001",
                },
            }
        },
    ),
) -> MatchResult:
    """Match an anonymous CandidateProfile against one job description."""
    return match_candidate_to_job(
        candidate=request.candidate,
        job_title=request.job_title,
        job_description=request.job_description,
        parse_status=request.parse_status,
        extraction_confidence=request.extraction_confidence,
        job_id=request.job_id,
    )


@router.get("/status", tags=["Agent 2 - Job Matching"])
def agent2_status() -> dict[str, str]:
    """Describe the Agent 2 service for the activity monitor."""
    return {"agent": "job_matching", "status": "ready"}
