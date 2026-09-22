from __future__ import annotations

from pathlib import Path

from backend.agents.agent1_candidate_intelligence.agent import CandidateIntelligenceAgent
from backend.agents.agent1_candidate_intelligence.llm import LLMEnhancer
from backend.agents.agent1_candidate_intelligence.pii import PIIDetector
from backend.config import Settings
from backend.security.files import UploadValidationError, validate_upload


def test_pii_is_redacted_without_raw_values() -> None:
    text = "Jane Doe\nEmail: jane.doe@example.com | Phone: +94 77 123 4567"
    report = PIIDetector(use_nlp=False).redact(text)

    assert report.detected_count >= 3
    assert "jane.doe@example.com" not in report.redacted_text
    assert "+94 77 123 4567" not in report.redacted_text


def test_upload_rejects_disguised_executable() -> None:
    try:
        validate_upload("resume.txt", b"MZ" + b"bad executable")
    except UploadValidationError as exc:
        assert "executable" in str(exc)
    else:
        raise AssertionError("Executable upload was accepted")


def test_llm_failure_falls_back_to_deterministic_profile(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(llm_provider="gemini", google_api_key="test-key", llm_model="test-model")
    agent = CandidateIntelligenceAgent(settings=settings, storage_dir=tmp_path)

    def fail(_: str) -> str:
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(agent.llm, "_call", fail)
    result = agent.process("resume.txt", b"PROFILE\nData Analyst with SQL experience.\nSKILLS\nSQL")

    assert result.extraction_method == "deterministic"
    assert any("deterministic extraction used" in warning for warning in result.warnings)