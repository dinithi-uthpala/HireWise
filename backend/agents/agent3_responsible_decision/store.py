"""Saving pipeline results and human decisions (+ their audit events)."""
from __future__ import annotations

from sqlmodel import Session, col, select

from backend.models_pipeline import CandidateRecord, HumanDecisionRecord
from backend.schemas import ExtractionResult, MatchResult, ReviewOutput

from .audit import now_iso, write_audit
from .contracts import CandidateSummary, HumanDecisionOut
from .decisions import is_override


def save_pipeline_result(session: Session, job_id: str, extraction: ExtractionResult,
                         match: MatchResult, review: ReviewOutput) -> CandidateRecord:
    """Store one candidate's full result and write the three agent audit events."""
    cid = extraction.candidate_id
    values = dict(
        job_id=job_id,
        extraction_json=extraction.model_dump_json(),
        match_json=match.model_dump_json(),
        review_json=review.model_dump_json(),
        match_score=review.match_score,
        recommendation_code=review.recommendation_code,
        recommendation=review.recommendation,
        extraction_confidence=review.extraction_confidence,
        risk_flag_codes=",".join(f.code for f in review.risk_flags),
        status="awaiting_human_review",
        final_decision="",
    )
    rec = session.get(CandidateRecord, cid)
    if rec is None:
        rec = CandidateRecord(candidate_id=cid, created_at=now_iso(), **values)
    else:
        for key, val in values.items():
            setattr(rec, key, val)
    session.add(rec)
    session.commit()
    session.refresh(rec)

    write_audit(session, cid, "agent1", "extracted", {
        "job_id": job_id,
        "extraction_confidence": extraction.extraction_confidence,
        "parse_status": extraction.parse_status,
        "pii_items_removed": extraction.pii.detected_count,
    })
    write_audit(session, cid, "agent2", "scored", {
        "job_id": job_id,
        "match_score": match.match_score,
        "match_status": match.match_status,
        "mandatory_gaps": [g.skill for g in match.skill_gaps if g.category == "mandatory"],
    })
    write_audit(session, cid, "agent3", "reviewed", {
        "job_id": job_id,
        "recommendation_code": review.recommendation_code,
        "risk_flags": [f.code for f in review.risk_flags],
        "privacy_check_passed": review.privacy_check.passed,
        "human_review_required": True,
    })
    return rec


def record_human_decision(session: Session, candidate_id: str, decision: str,
                          note: str, decided_by: str) -> HumanDecisionRecord:
    """Save the recruiter's decision. Raises LookupError / ValueError."""
    rec = session.get(CandidateRecord, candidate_id)
    if rec is None:
        raise LookupError(f"Candidate {candidate_id} not found")

    override = is_override(rec.recommendation_code, decision)
    if override and not note.strip():
        raise ValueError(
            "A note is required when the decision differs from the AI recommendation."
        )

    row = HumanDecisionRecord(
        candidate_id=candidate_id, job_id=rec.job_id, decision=decision, note=note,
        decided_by=decided_by, ai_recommendation_code=rec.recommendation_code,
        is_override=override, ts=now_iso(),
    )
    rec.status = "decided"
    rec.final_decision = decision
    session.add(row)
    session.add(rec)
    session.commit()
    session.refresh(row)

    # The note is NOT copied into the audit log (it may contain personal remarks).
    write_audit(session, candidate_id, f"user:{decided_by}", "human_decision", {
        "decision": decision,
        "is_override": override,
        "ai_recommendation_code": rec.recommendation_code,
        "note_provided": bool(note.strip()),
    })
    return row


def list_candidates(session: Session, job_id: str) -> list[CandidateRecord]:
    rows = list(session.exec(select(CandidateRecord).where(CandidateRecord.job_id == job_id)).all())
    rows.sort(key=lambda r: (r.match_score is None, -(r.match_score or 0.0)))
    return rows


def decisions_for(session: Session, candidate_id: str) -> list[HumanDecisionRecord]:
    stmt = (select(HumanDecisionRecord)
            .where(HumanDecisionRecord.candidate_id == candidate_id)
            .order_by(col(HumanDecisionRecord.id)))
    return list(session.exec(stmt).all())


# ---- record -> API model converters --------------------------------------
def to_summary(rec: CandidateRecord) -> CandidateSummary:
    return CandidateSummary(
        candidate_id=rec.candidate_id, job_id=rec.job_id, match_score=rec.match_score,
        recommendation_code=rec.recommendation_code, recommendation=rec.recommendation,
        extraction_confidence=rec.extraction_confidence,
        risk_flag_codes=[c for c in rec.risk_flag_codes.split(",") if c],
        status=rec.status, final_decision=rec.final_decision,
    )


def to_decision_out(row: HumanDecisionRecord) -> HumanDecisionOut:
    return HumanDecisionOut(
        candidate_id=row.candidate_id, job_id=row.job_id, decision=row.decision,
        note=row.note, decided_by=row.decided_by,
        ai_recommendation_code=row.ai_recommendation_code,
        is_override=row.is_override, ts=row.ts,
    )
