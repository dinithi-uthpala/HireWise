"""Pure hash-chain helpers for the audit log (no database code here)."""
from __future__ import annotations

import hashlib

GENESIS_HASH = "0" * 64


def compute_entry_hash(prev_hash: str, candidate_id: str, actor: str,
                       action: str, summary_json: str, ts: str) -> str:
    payload = "|".join([prev_hash, candidate_id, actor, action, summary_json, ts])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(rows) -> tuple[bool, int | None]:
    """rows must be ordered by id. Returns (is_valid, first_bad_row_id)."""
    prev = GENESIS_HASH
    for r in rows:
        expected = compute_entry_hash(prev, r.candidate_id, r.actor, r.action, r.summary_json, r.ts)
        if r.prev_hash != prev or r.entry_hash != expected:
            return False, r.id
        prev = r.entry_hash
    return True, None
