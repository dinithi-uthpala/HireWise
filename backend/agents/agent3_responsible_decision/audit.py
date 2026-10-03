"""Audit log writer/reader. Each entry is chained to the previous one by hash."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, col, select

from backend.models_pipeline import AuditLog

from .audit_chain import GENESIS_HASH, compute_entry_hash, verify_chain


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_audit(session: Session, candidate_id: str, actor: str, action: str,
                summary: dict[str, Any] | None = None) -> AuditLog:
    """Append one audit event. `summary` must never contain raw personal data."""
    last = session.exec(select(AuditLog).order_by(col(AuditLog.id).desc())).first()
    prev_hash = last.entry_hash if last else GENESIS_HASH
    summary_json = json.dumps(summary or {}, sort_keys=True, default=str)
    ts = now_iso()
    row = AuditLog(
        candidate_id=candidate_id, actor=actor, action=action,
        summary_json=summary_json, prev_hash=prev_hash, ts=ts,
        entry_hash=compute_entry_hash(prev_hash, candidate_id, actor, action, summary_json, ts),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def audit_trail(session: Session, candidate_id: str) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.candidate_id == candidate_id).order_by(col(AuditLog.id))
    return list(session.exec(stmt).all())


def verify_audit_chain(session: Session) -> tuple[bool, int, int | None]:
    """Check the WHOLE log. Returns (valid, entries_checked, first_bad_id)."""
    rows = list(session.exec(select(AuditLog).order_by(col(AuditLog.id))).all())
    ok, bad_id = verify_chain(rows)
    return ok, len(rows), bad_id
