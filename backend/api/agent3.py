"""Agent 3 REST API: review, candidate results, human decisions, audit, fairness."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from backend.agents.agent3_responsible_decision import review_candidate
from backend.agents.agent3_responsible_decision.audit import audit_trail, verify_audit_chain
from backend.agents.agent3_responsible_decision.contracts import (
    AuditEventOut,
    AuditVerifyOut,
    CandidateDetail,
    CandidateSummary,
    FairnessRequest,
    FairnessTestResult,
    HumanDecisionIn,
    HumanDecisionOut,
    ReviewRequest,
)
from backend.agents.agent3_responsible_decision.fairness import compare_reviews
from backend.agents.agent3_responsible_decision.settings_bridge import thresholds_from_settings
from backend.agents.agent3_responsible_decision.store import (
    decisions_for,
    list_candidates,
    record_human_decision,
    to_decision_out,
    to_summary,
)
from backend.api.deps import get_actor
from backend.database import get_session
from backend.models_pipeline import CandidateRecord
from backend.schemas import ExtractionResult, MatchResult, ReviewOutput

router = APIRouter(tags=["Agent 3 - Responsible Decision"])


@router.get("/agent3/status")
def agent3_status() -> dict:
    th = thresholds_from_settings()
    return {"agent": "Responsible Decision Agent", "status": "ok",
            "thresholds": th.model_dump(), "makes_final_decision": False}


@router.post("/agent3/review", response_model=ReviewOutput)
def review(payload: ReviewRequest) -> ReviewOutput:
    """Stateless review: Agent 1 + Agent 2 results in, recommendation out."""
    return review_candidate(payload.extraction, payload.match, thresholds_from_settings())


@router.post("/agent3/fairness-compare", response_model=FairnessTestResult)
def fairness_compare(payload: FairnessRequest) -> FairnessTestResult:
    return compare_reviews(payload.cv_a_label, payload.cv_b_label,
                           payload.review_a, payload.review_b, payload.tolerance)


@router.get("/jobs/{job_id}/candidates", response_model=list[CandidateSummary])
def candidates_for_job(job_id: str, session: Session = Depends(get_session)) -> list[CandidateSummary]:
    return [to_summary(r) for r in list_candidates(session, job_id)]


@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
def candidate_detail(candidate_id: str, session: Session = Depends(get_session)) -> CandidateDetail:
    rec = session.get(CandidateRecord, candidate_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateDetail(
        summary=to_summary(rec),
        extraction=ExtractionResult.model_validate_json(rec.extraction_json),
        match=MatchResult.model_validate_json(rec.match_json),
        review=ReviewOutput.model_validate_json(rec.review_json),
        decisions=[to_decision_out(d) for d in decisions_for(session, candidate_id)],
    )


@router.post("/candidates/{candidate_id}/decision", response_model=HumanDecisionOut)
def submit_decision(candidate_id: str, body: HumanDecisionIn,
                    session: Session = Depends(get_session),
                    actor: str = Depends(get_actor)) -> HumanDecisionOut:
    try:
        row = record_human_decision(session, candidate_id, body.decision, body.note, actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return to_decision_out(row)


@router.get("/audit/{candidate_id}", response_model=list[AuditEventOut])
def audit_for_candidate(candidate_id: str, session: Session = Depends(get_session)) -> list[AuditEventOut]:
    return [
        AuditEventOut(id=r.id, candidate_id=r.candidate_id, actor=r.actor, action=r.action,
                      summary=json.loads(r.summary_json or "{}"), ts=r.ts, entry_hash=r.entry_hash)
        for r in audit_trail(session, candidate_id)
    ]


@router.get("/audit-chain/verify", response_model=AuditVerifyOut)
def verify_audit(session: Session = Depends(get_session)) -> AuditVerifyOut:
    ok, count, bad_id = verify_audit_chain(session)
    return AuditVerifyOut(valid=ok, entries_checked=count, first_bad_entry_id=bad_id)
