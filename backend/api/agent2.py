"""FastAPI endpoints for the Job Matching & Retrieval Agent."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.agents.agent2_job_matching.agent import match_candidate_to_job
from backend.agents.agent2_job_matching.requirements import (
    extract_job_requirements,
)
from backend.database import get_session
from backend.job_catalog import CATALOG_JOBS
from backend.models import JobVacancy
from backend.schemas import (
    CandidateProfile,
    JobCreate,
    JobOut,
    MatchResult,
)


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
            "Required skills: Python, SQL, Excel. "
            "Preferred skills: Pandas, Power BI. "
            "Minimum 1 year of relevant experience. "
            "Bachelor's degree required."
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
        description=(
            "Persisted job identifier. When supplied, the stored job title "
            "and description are used for matching."
        ),
        examples=["JOB-001"],
    )


router = APIRouter(
    prefix="/agent2",
    tags=["Agent 2 - Job Matching"],
)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(session: Session = Depends(get_session)) -> list[JobOut]:
    """Return the curated built-in job library for recruiter selection."""
    jobs_by_id = {
        job.job_id: job
        for job in session.exec(select(JobVacancy)).all()
        if job.job_id in {item.job_id for item in CATALOG_JOBS}
    }
    unique_jobs = [jobs_by_id[item.job_id] for item in CATALOG_JOBS if item.job_id in jobs_by_id]
    unique_jobs.sort(key=lambda job: job.job_title.lower())
    return [
        JobOut(
            job_id=job.job_id,
            job_title=job.job_title,
            job_description=job.job_description,
            created_at=job.created_at,
        )
        for job in unique_jobs
    ]


# ---------------------------------------------------------------------
# Create Job
# ---------------------------------------------------------------------

@router.post(
    "/jobs",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    request: JobCreate,
    session: Session = Depends(get_session),
) -> JobOut:
    """Create a persisted vacancy for Agent 2 matching."""

    job_id = request.job_id or f"JOB-{uuid4().hex[:12].upper()}"

    if session.get(JobVacancy, job_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job ID '{job_id}' already exists.",
        )

    job = JobVacancy(
        job_id=job_id,
        job_title=request.job_title,
        job_description=request.job_description,
    )

    session.add(job)
    session.commit()
    session.refresh(job)

    return JobOut(
        job_id=job.job_id,
        job_title=job.job_title,
        job_description=job.job_description,
        created_at=job.created_at,
    )


# ---------------------------------------------------------------------
# Get Job Requirements
# ---------------------------------------------------------------------

@router.get(
    "/jobs/{job_id}/requirements",
)
def get_job_requirements(
    job_id: str,
    session: Session = Depends(get_session),
):
    """
    Extract and return normalized requirements for a persisted job.

    The extraction is deterministic and reuses Agent 2's existing
    requirement-extraction logic.
    """

    stored_job = session.get(JobVacancy, job_id)

    if stored_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job ID '{job_id}' was not found.",
        )

    requirements, warnings = extract_job_requirements(
        title=stored_job.job_title,
        description=stored_job.job_description,
        job_id=stored_job.job_id,
    )

    return {
        "requirements": requirements,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------
# Match Candidate
# ---------------------------------------------------------------------

@router.post(
    "/match",
    response_model=MatchResult,
)
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
                        "soft_skills": [
                            "Communication",
                            "Teamwork",
                        ],
                        "job_titles": [
                            "Junior Data Analyst",
                        ],
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
                        "summary": (
                            "Junior Data Analyst with reporting experience."
                        ),
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
    session: Session = Depends(get_session),
) -> MatchResult:
    """Match an anonymous CandidateProfile against one job description."""

    job_title = request.job_title
    job_description = request.job_description

    # -------------------------------------------------------------
    # Persisted-job matching
    # -------------------------------------------------------------

    if request.job_id and not (
        job_title.strip() or job_description.strip()
    ):
        stored_job = session.get(
            JobVacancy,
            request.job_id,
        )

        if stored_job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job ID '{request.job_id}' was not found.",
            )

        job_title = stored_job.job_title
        job_description = stored_job.job_description

    # -------------------------------------------------------------
    # Agent 2 matching + deterministic scoring
    # -------------------------------------------------------------

    return match_candidate_to_job(
        candidate=request.candidate,
        job_title=job_title,
        job_description=job_description,
        parse_status=request.parse_status,
        extraction_confidence=request.extraction_confidence,
        job_id=request.job_id,
    )


# ---------------------------------------------------------------------
# Agent 2 Status
# ---------------------------------------------------------------------

@router.get(
    "/status",
    tags=["Agent 2 - Job Matching"],
)
def agent2_status() -> dict[str, str]:
    """Describe the Agent 2 service for the activity monitor."""

    return {
        "agent": "job_matching",
        "status": "ready",
    }