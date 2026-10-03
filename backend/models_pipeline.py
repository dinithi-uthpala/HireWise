"""Database tables for the candidate pipeline, human decisions and audit trail.

Kept in its own file (not models.py) so three people can edit tables without
merge conflicts. main.py imports this module so the tables are created.
"""
from __future__ import annotations

from sqlmodel import Field, SQLModel


class CandidateRecord(SQLModel, table=True):
    """One processed CV: the three agents' results stored as JSON text.

    Deliberately stores NO original file name (file names often contain the
    candidate's name). The original CV lives encrypted in storage/cvs/.
    """

    candidate_id: str = Field(primary_key=True, max_length=100)
    job_id: str = Field(index=True, max_length=100)
    extraction_json: str = ""            # Agent 1 ExtractionResult
    match_json: str = ""                 # Agent 2 MatchResult
    review_json: str = ""                # Agent 3 ReviewOutput
    match_score: float | None = None
    recommendation_code: str = ""
    recommendation: str = ""
    extraction_confidence: float = 0.0
    risk_flag_codes: str = ""            # comma separated
    status: str = "awaiting_human_review"   # awaiting_human_review | decided
    final_decision: str = ""             # latest human decision
    created_at: str = ""                 # ISO timestamp (UTC)


class HumanDecisionRecord(SQLModel, table=True):
    """The recruiter's decision. The AI never writes to this table."""

    id: int | None = Field(default=None, primary_key=True)
    candidate_id: str = Field(index=True, max_length=100)
    job_id: str = ""
    decision: str                        # shortlist | hold | not_selected
    note: str = ""
    decided_by: str = ""
    ai_recommendation_code: str = ""
    is_override: bool = False            # human disagreed with the AI
    ts: str = ""


class AuditLog(SQLModel, table=True):
    """Append-only, hash-chained audit trail (tamper-evident).

    entry_hash = SHA-256(prev_hash + this row's content). Changing or deleting
    any old row breaks every hash after it, which verify_audit_chain() detects.
    """

    id: int | None = Field(default=None, primary_key=True)
    candidate_id: str = Field(index=True, max_length=100)
    actor: str = ""                      # agent1 | agent2 | agent3 | user:<name>
    action: str = ""                     # extracted | scored | reviewed | human_decision
    summary_json: str = "{}"             # NO raw personal data, ever
    prev_hash: str = ""
    entry_hash: str = ""
    ts: str = ""                         # stored as text so the hash is stable
