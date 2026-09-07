"""FastAPI endpoints for the Candidate Intelligence Agent."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.agents.agent1_candidate_intelligence import process_cv
from backend.security.files import UploadValidationError
from backend.schemas import ExtractionResult

router = APIRouter(prefix="/agent1", tags=["Agent 1 - Candidate Intelligence"])


@router.post("/process", response_model=ExtractionResult)
async def process_candidate_cv(
    file: UploadFile = File(..., description="PDF, DOCX, TXT, or Markdown CV"),
) -> ExtractionResult:
    """Process one CV and return only the anonymous Agent 1 result."""
    filename = file.filename or ""
    if not filename.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required.")

    data = await file.read()
    try:
        return process_cv(filename, data)
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/process-batch", response_model=list[ExtractionResult])
async def process_candidate_batch(
    files: list[UploadFile] = File(..., description="One or more CV documents"),
) -> list[ExtractionResult]:
    """Process multiple CVs independently, preserving one result per file."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one CV is required.")

    results: list[ExtractionResult] = []
    for file in files:
        filename = file.filename or ""
        if not filename.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Every upload needs a filename.")
        data = await file.read()
        try:
            results.append(process_cv(filename, data))
        except UploadValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename}: {exc}",
            ) from exc
    return results


@router.get("/status", tags=["Agent 1 - Candidate Intelligence"])
def agent1_status() -> dict[str, str]:
    """Describe the Agent 1 service for the activity monitor."""
    return {"agent": "candidate_intelligence", "status": "ready"}