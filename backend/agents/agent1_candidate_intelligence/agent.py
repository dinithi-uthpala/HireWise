"""Candidate Intelligence Agent - orchestration (Agent 1).

End-to-end pipeline for one CV:

    1. upload validation        (type / size / malware-safe rules)
    2. text extraction          (PDF | DOCX | TXT)
    3. untrusted-data guard     (prompt-injection neutralization)
    4. PII detection + redaction (privacy boundary before anything else)
    5. structured profile       (deterministic NLP, optional LLM enhancement)
    6. confidence + warnings    (honest uncertainty reporting)
    7. secure storage           (original CV encrypted at rest)
    8. ExtractionResult         -> sent to Agent 2 (never the raw document)

The agent NEVER returns identity data downstream: Agent 2 receives only the
anonymous :class:`CandidateProfile` plus the PII report (counts, no values).
"""
from __future__ import annotations

import logging
from pathlib import Path

from backend.config import STORAGE_CVS_DIR, Settings, get_settings
from backend.security.files import (
    UploadValidationError,
    sha256_bytes,
    store_encrypted,
    validate_upload,
)
from backend.security.sanitize import (
    contains_suspicious_instruction,
    strip_prompt_injections,
)
from backend.schemas import ExtractionResult

from .confidence import (
    compute_confidence,
    parse_status_for,
    warnings_for,
)
from .llm import LLMEnhancer, merge_llm_profile
from .pii import PIIDetector
from .profile_extraction import extract_profile
from .text_extraction import TextExtractionError, extract_text

logger = logging.getLogger("hirewise.agent1")


class CandidateIntelligenceAgent:
    """Agent 1 - converts a CV into an anonymous structured profile."""

    def __init__(self, settings: Settings | None = None,
                 storage_dir: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage_dir = Path(storage_dir) if storage_dir else STORAGE_CVS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.pii_detector = PIIDetector()
        self.llm = LLMEnhancer(self.settings)

    # ------------------------------------------------------------------
    def process(self, filename: str, data: bytes,
                candidate_id: str | None = None) -> ExtractionResult:
        """Run the full Agent 1 pipeline for one uploaded CV."""
        candidate_id = candidate_id or self.new_candidate_id(data)

        # 1. intake boundary -------------------------------------------------
        validate_upload(filename, data)          # raises UploadValidationError

        # 2. text extraction ------------------------------------------------
        try:
            raw_text = extract_text(data, filename.rsplit(".", 1)[-1])
        except TextExtractionError as exc:
            logger.info("Unreadable document (%s): %s", candidate_id, exc)
            return self._failed_result(candidate_id, data, str(exc))

        # 3. treat CV content as untrusted data ---------------------------------
        text = strip_prompt_injections(raw_text)
        warnings: list[str] = []
        if contains_suspicious_instruction(raw_text):
            warnings.append(
                "CV contained instruction-like content; it was neutralized "
                "before parsing (prompt-injection guard)."
            )

        # 4. PII redaction - the privacy boundary --------------------------------
        pii_report = self.pii_detector.redact(text)
        redacted_text = pii_report.redacted_text

        # 5. structured profile -------------------------------------------------
        profile = extract_profile(candidate_id, redacted_text)
        method = "deterministic"
        if self.llm.available():
            profile, method = merge_llm_profile(
                profile, self.llm.extract(redacted_text)
            )
            if self.llm.last_error:
                warnings.append(self.llm.last_error)

        # 6. confidence + warnings ------------------------------------------------
        confidence = compute_confidence(redacted_text, profile)
        warnings += warnings_for(redacted_text, profile, pii_found=pii_report.detected_count > 0)
        parse_status = parse_status_for(
            confidence, redacted_text, self.settings.low_confidence_threshold
        )

        # 7. store the original encrypted at rest -------------------------------------
        stored_path = store_encrypted(self.storage_dir, candidate_id, data)

        # 8. contract payload -------------------------------------------------------------
        return ExtractionResult(
            candidate_id=candidate_id,
            profile=profile,
            pii=pii_report,
            extraction_confidence=confidence,
            parse_status=parse_status,
            extraction_method=method,
            warnings=warnings,
            source_hash=sha256_bytes(data),
            stored_cv_path=stored_path,
        )

    # ------------------------------------------------------------------
    def _failed_result(self, candidate_id: str, data: bytes, reason: str) -> ExtractionResult:
        """Uniform result for unreadable documents (flagged, never crashed)."""
        return ExtractionResult(
            candidate_id=candidate_id,
            profile=extract_profile(candidate_id, ""),
            pii=self.pii_detector.redact(""),
            extraction_confidence=0.0,
            parse_status="failed",
            extraction_method="deterministic",
            warnings=[reason],
            source_hash=sha256_bytes(data),
            stored_cv_path="",
        )

    # ------------------------------------------------------------------
    def new_candidate_id(self, data: bytes) -> str:
        """Stable candidate id derived from the document hash (CAND-000000)."""
        digest = sha256_bytes(data)
        number = int(digest[:8], 16) % 1_000_000
        return f"{self.settings.candidate_id_prefix}-{number:06d}"


# ---------------------------------------------------------------------------
# Module-level convenience for the API layer / other agents
# ---------------------------------------------------------------------------
_default_agent: CandidateIntelligenceAgent | None = None


def get_agent() -> CandidateIntelligenceAgent:
    """Process-wide shared Agent 1 instance."""
    global _default_agent
    if _default_agent is None:
        _default_agent = CandidateIntelligenceAgent()
    return _default_agent


def process_cv(filename: str, data: bytes, candidate_id: str | None = None) -> ExtractionResult:
    """One-call helper: process a CV with the shared agent instance."""
    return get_agent().process(filename, data, candidate_id)


__all__ = [
    "CandidateIntelligenceAgent",
    "UploadValidationError",
    "TextExtractionError",
    "get_agent",
    "process_cv",
]
# ---APPEND-MARKER---