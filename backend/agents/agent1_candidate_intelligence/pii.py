"""PII detection and redaction (Agent 1).

Detects and removes personally identifiable information from CV text so the
*anonymous* profile sent to Agent 2 can never leak identity.

Combination of:
  - regex patterns  (email, phone, NIC/passport, DOB, age, address, ...)
  - context keywords (label-led lines: "Address:", "Marital Status:", ...)
  - optional spaCy NER (PERSON spans, only within the header block)
  - a first-line heuristic for the classic "Jane Doe" header

Every detected span is replaced with a safe placeholder such as ``[NAME]``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.schemas import PIIItem, PIIReport

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Phone: "+94 77 123 4567", "0771234567", "011 234 5678"
_PHONE_RE = re.compile(
    r"(?<!\d)(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{6,8})(?!\d)"
)

# Sri Lankan NIC: 9 digits + V/v, or 12 digits (19xx/20xx)
_NIC_RE = re.compile(r"\b(?:\d{9}[Vv]|(?:19|20)\d{10})\b")

# Label-led lines (capture the value after the colon)
_LABEL_LINE_RE = re.compile(
    r"(?im)^\s*[-•▪◦*]?\s*"
    r"(?P<label>name|full\s*name|date\s*of\s*birth|\bdob\b|birth\s*date|"
    r"address|residence|current\s*address|postal\s*address|"
    r"nationality|citizenship|religion|ethnicity|race|marital\s*status|"
    r"gender|sex|passport(?:\s*(?:no\.?|number|#))?|nic(?:\s*(?:no\.?|number|#))?|"
    r"id(?:\s*(?:no\.?|number|#))?|identification(?:\s*no\.?)?)"
    r"\s*[:.\-\u2013\u2014]?\s*(?P<value>.+?)\s*$"
)

# "Age: 28" / "28 years old"
_AGE_RE = re.compile(
    r"(?i)\b(?:age|aged)\s*[:.\-\u2013\u2014]?\s*(\d{1,3})\b|\b(\d{1,3})\s*years?\s*old\b"
)

# Standalone gender keywords
_GENDER_RE = re.compile(r"(?i)\b(?:male|female|non[- ]binary)\b")
# Gender-implying honorifics (professional titles Dr/Prof/Eng are kept)
_HONORIFIC_RE = re.compile(r"(?i)\b(?:mr|mrs|ms|miss|mx)\.?\b")

# Conservative religion / ethnicity / nationality keywords -- only single
# unambiguous terms so regular sentences are not destroyed.
_RELIGION_RE = re.compile(
    r"(?i)\b(?:buddhism|christianity|catholicism|islam|hinduism|judaism)\b"
)
_MARITAL_RE = re.compile(
    r"(?m)(?:^|\n)\s*[-•▪◦*]?\s*(?:Married|Unmarried|Divorced|Widowed)(?:\s|$)"
)
_DISABILITY_RE = re.compile(r"(?i)\b(?:disabilit(?:y|ies)|disabl(?:ed|ement))\b")

# University / institute names (institution is restricted from scoring)
_UNIVERSITY_RE = re.compile(
    r"(?i)\b(?:university\s+of\s+[A-Z][\w'.\-]*(?:\s+[A-Z][\w'.\-]*){0,2}"
    r"|[\w'.\-]+\s+university(?!\s+of)"
    r"|(?:[\w'\-.]+){1,2}\s+(?:institute|college|academy)\s+of\s+technology"
    r"|[\w'.\-]+\s+(?:technical\s+college|university\s+college|institute\s+of\s+technology))\b"
)

# Header block: first N lines where a personal name usually lives.
_HEADER_LINES = 6
_HEADER_WORDS = {
    "curriculum", "vitae", "resume", "cv", "profile", "summary", "objective",
    "experience", "education", "skills", "contact", "page",
}

# Threat-model placeholders (kept short so the redacted text stays readable).
_PLACEHOLDER: dict[str, str] = {
    "name": "[NAME]",
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "nic": "[NATIONAL_ID]",
    "passport": "[PASSPORT]",
    "address": "[ADDRESS]",
    "dob": "[DOB]",
    "age": "[AGE]",
    "gender": "[GENDER]",
    "religion": "[RELIGION]",
    "ethnicity": "[ETHNICITY]",
    "marital_status": "[MARITAL_STATUS]",
    "disability": "[DISABILITY]",
    "nationality": "[NATIONALITY]",
    "university": "[UNIVERSITY]",
}


@dataclass(slots=True)
class _Span:
    start: int
    end: int
    pii_type: str

    def overlap(self, other: "_Span") -> bool:
        return self.start < other.end and other.start < self.end