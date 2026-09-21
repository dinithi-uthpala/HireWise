"""Pipeline API: ONE call runs Agent 1 -> Agent 2 -> Agent 3 and saves the result.

    POST /api/pipeline/run            upload CVs for a job, get a recommendation per CV
    POST /api/pipeline/fairness-test  run a paired-CV fairness test (nothing is saved
                                      as a candidate; only an audit event is written)

The three agents talk through the typed contracts in backend/schemas.py:
    ExtractionResult (Agent 1) -> MatchResult (Agent 2) -> ReviewOutput (Agent 3)
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session

from backend.agents.agent1_candidate_intelligence import process_cv
from backend.agents.agent2_job_matching.agent import match_candidate_to_job
from backend.agents.agent3_responsible_decision import review_candidate
from backend.agents.agent3_responsible_decision.audit import write_audit
from backend.agents.agent3_responsible_decision.contracts import (
    CandidateSummary,
    FairnessTestResult,
)
from backend.agents.agent3_responsible_decision.fairness import compare_reviews
from backend.agents.agent3_responsible_decision.settings_bridge import thresholds_from_settings
from backend.agents.agent3_responsible_decision.store import save_pipeline_result, to_summary
from backend.database import get_session
from backend.models import JobVacancy
from backend.schemas import ExtractionResult, MatchResult, ReviewOutput, ReviewThresholds
from backend.security.files import UploadValidationError

logger = logging.getLogger("hirewise.pipeline")

router = APIRouter(prefix="/pipeline", tags=["Pipeline - Agent 1 -> 2 -> 3"])


class PipelineItem(BaseModel):
    """Result for ONE uploaded file. `filename` is only echoed back so the
    dashboard can line results up with uploads; it is never stored."""

    filename: str
    status: Literal["processed", "error"]
    candidate: CandidateSummary | None = None
    error: str = ""


def run_agents(filename: str, data: bytes, job: JobVacancy,
               thresholds: ReviewThresholds) -> tuple[ExtractionResult, MatchResult, ReviewOutput]:
    """The whole agent chain for one CV (no database access)."""
    extraction = process_cv(filename, data)                       # Agent 1
    match = match_candidate_to_job(                               # Agent 2
        candidate=extraction.profile,
        job_title=job.job_title,
        job_description=job.job_description,
        parse_status=extraction.parse_status,
        extraction_confidence=extraction.extraction_confidence,
        job_id=job.job_id,
    )
    review = review_candidate(extraction, match, thresholds)      # Agent 3
    return extraction, match, review


def _get_job_or_404(session: Session, job_id: str) -> JobVacancy:
    job = session.get(JobVacancy, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' was not found. Create it first (POST /api/agent2/jobs).",
        )
    return job


@router.post("/run", response_model=list[PipelineItem])
async def run_pipeline(
    job_id: str = Form(...),
    files: list[UploadFile] = File(..., description="One or more CVs (PDF, DOCX, TXT, MD)"),
    session: Session = Depends(get_session),
) -> list[PipelineItem]:
    """Process each CV independently. One bad file never stops the others."""
    job = _get_job_or_404(session, job_id)
    thresholds = thresholds_from_settings()

    items: list[PipelineItem] = []
    for upload in files:
        name = (upload.filename or "").strip()
        data = await upload.read()
        if not name:
            items.append(PipelineItem(filename="(no name)", status="error",
                                      error="Every upload needs a filename."))
            continue
        try:
            extraction, match, review = run_agents(name, data, job, thresholds)
            record = save_pipeline_result(session, job_id, extraction, match, review)
            items.append(PipelineItem(filename=name, status="processed",
                                      candidate=to_summary(record)))
        except UploadValidationError as exc:
            items.append(PipelineItem(filename=name, status="error", error=str(exc)))
        except Exception as exc:  # keep the batch going; never log CV content
            logger.error("Pipeline failed for one CV (%s)", type(exc).__name__)
            items.append(PipelineItem(
                filename=name, status="error",
                error=f"This CV could not be processed ({type(exc).__name__}).",
            ))
    return items


@router.post("/fairness-test", response_model=FairnessTestResult)
async def fairness_test(
    job_id: str = Form(...),
    tolerance: float = Form(0.5),
    file_a: UploadFile = File(..., description="CV A"),
    file_b: UploadFile = File(..., description="CV B: same qualifications, different identity"),
    session: Session = Depends(get_session),
) -> FairnessTestResult:
    """Run two CVs through the full pipeline and check they get the same outcome."""
    job = _get_job_or_404(session, job_id)
    thresholds = thresholds_from_settings()

    reviews: list[ReviewOutput] = []
    for upload in (file_a, file_b):
        name = (upload.filename or "").strip() or "cv"
        data = await upload.read()
        try:
            _, _, review = run_agents(name, data, job, thresholds)
        except UploadValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        reviews.append(review)

    result = compare_reviews("CV A", "CV B", reviews[0], reviews[1], tolerance)
    write_audit(session, "FAIRNESS-TEST", "agent3", "fairness_test", {
        "job_id": job_id, "score_a": result.score_a, "score_b": result.score_b,
        "difference": result.difference, "passed": result.passed,
    })
    return result
