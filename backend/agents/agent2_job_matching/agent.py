"""Main orchestration for the Agent 2 job-matching pipeline."""
from __future__ import annotations

from typing import Literal

from backend.schemas import CandidateProfile, MatchResult

from .requirements import extract_job_requirements
from .retrieval import retrieve_job_evidence
from .scoring import score_candidate

ParseStatus = Literal["ok", "low_confidence", "failed"]


def match_candidate_to_job(
    candidate: CandidateProfile,
    job_title: str,
    job_description: str,
    parse_status: ParseStatus,
    extraction_confidence: float,
    job_id: str = "",
) -> MatchResult:
    """Match an Agent 1 profile to a job using deterministic Agent 2 logic.

    Only the anonymous ``CandidateProfile`` and Agent 1's status metadata are
    consumed. Requirement extraction runs before the status gate so its
    warnings are preserved even when matching is unavailable.
    """
    if parse_status not in {"ok", "low_confidence", "failed"}:
        raise ValueError(f"Unsupported parse_status: {parse_status}")

    job, requirement_warnings = extract_job_requirements(
        title=job_title,
        description=job_description,
        job_id=job_id,
    )

    if parse_status == "failed":
        return MatchResult(
            candidate_id=candidate.candidate_id,
            job_id=job.job_id,
            parse_status="failed",
            match_status="unavailable",
            extraction_confidence=extraction_confidence,
            match_score=None,
            warnings=requirement_warnings + [
                "Matching is unavailable because candidate extraction failed."
            ],
        )

    try:
        retrieval_evidence, retrieval_warnings = retrieve_job_evidence(job)
    except Exception:
        retrieval_evidence, retrieval_warnings = [], [
            "Knowledge-base retrieval was unavailable; deterministic scoring continued."
        ]
    result = score_candidate(candidate, job, retrieval_evidence=retrieval_evidence)
    result.parse_status = parse_status
    result.extraction_confidence = extraction_confidence
    if result.match_status == "scored":
        result.match_status = "warning" if parse_status == "low_confidence" else "scored"
    result.retrieval_evidence = retrieval_evidence
    result.warnings = list(result.warnings) + requirement_warnings + retrieval_warnings

    if parse_status == "low_confidence":
        result.warnings.append(
            "Candidate information was extracted with low confidence; review the match manually."
        )

    return result
