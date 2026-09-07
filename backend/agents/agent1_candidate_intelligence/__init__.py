"""Agent 1 - Candidate Intelligence Agent.

Converts an unstructured CV into a clean, anonymous, structured profile.
Responsibilities:
    - file type/size validation
    - PDF / DOCX / TXT text extraction
    - NLP/LLM structured extraction (skills, experience, education, ...)
    - PII detection & anonymization (name, email, phone, address, ...)
    - extraction-confidence score + warnings
    - write audit + agent-activity events

Input : candidate CV (PDF/DOCX) + candidate_id
Output: ExtractionResult (anonymous CandidateProfile + PIIReport)
"""

# TODO(Team member 1): implement extractors, PII redaction and extraction.