"""Agent 1 - Candidate Intelligence Agent.

Converts an unstructured CV into a clean, anonymous, structured profile.
Responsibilities:
    - file type/size validation          -> security/files.py
    - PDF / DOCX / TXT text extraction   -> text_extraction.py
    - NLP/LLM structured extraction      -> profile_extraction.py + llm.py
    - PII detection & anonymization      -> pii.py
    - extraction-confidence score        -> confidence.py
    - orchestration + secure storage     -> agent.py

Input : candidate CV (PDF/DOCX/TXT) + optional candidate_id
Output: ExtractionResult (anonymous CandidateProfile + PIIReport)

Usage (from the repository root):
    from backend.agents.agent1_candidate_intelligence import process_cv
    result = process_cv("cv.pdf", pdf_bytes)          # -> ExtractionResult
"""

from backend.agents.agent1_candidate_intelligence.agent import (
    CandidateIntelligenceAgent,
    TextExtractionError,
    get_agent,
    process_cv,
)

__all__ = [
    "CandidateIntelligenceAgent",
    "TextExtractionError",
    "get_agent",
    "process_cv",
]