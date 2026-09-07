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

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
class PIIDetector:
    """Detects and redacts PII in CV text.

    Args:
        use_nlp: when True (and a spaCy model is installed) PERSON spans are
            used as an additional signal inside the header block.
    """

    def __init__(self, use_nlp: bool = True) -> None:
        self.use_nlp = use_nlp
        self._nlp = None
        if use_nlp:
            self._load_nlp()

    def _load_nlp(self) -> None:
        """Load spaCy NER if available (optional dependency + model)."""
        try:
            import spacy

            self._nlp = spacy.load(
                "en_core_web_sm", disable=("parser", "tagger", "attribute_ruler", "lemmatizer")
            )
        except Exception:
            self._nlp = None  # rules-only mode

    # -- public API -----------------------------------------------------------
    def detect(self, text: str) -> list[PIIItem]:
        """Detect PII and return the privacy report items (no redaction)."""
        return [_Span_to_item(s, text) for s in self._detect_spans(text)]

    def redact(self, text: str) -> PIIReport:
        """Detect PII and produce a :class:`PIIReport` with the redacted text."""
        spans = _merge_spans(self._detect_spans(text))
        redacted = _apply_spans(text, spans)
        items = [_Span_to_item(s, text) for s in spans]
        return PIIReport(
            detected_count=len(items),
            items=items,
            redacted_text=redacted,
        )

    # -- detection ------------------------------------------------------------
    def _detect_spans(self, text: str) -> list[_Span]:
        spans: list[_Span] = []
        spans += _emails(text)
        spans += _phones(text)
        spans += _nic_spans(text)
        spans += _age_spans(text)
        spans += _gender_spans(text)
        spans += _honorific_spans(text)
        spans += _religion_spans(text)
        spans += _marital_spans(text)
        spans += _disability_spans(text)
        spans += _university_spans(text)
        spans += _label_led_spans(text)
        spans += self._name_spans(text)
        return spans

    def _name_spans(self, text: str) -> list[_Span]:
        """Name detection: spaCy NER (header block) + first-line heuristic."""
        spans: list[_Span] = []
        if self._nlp is not None:
            doc = self._nlp(text[:1200])
            for ent in doc.ents:
                if ent.label_ == "PERSON" and text.count("\n", 0, ent.start_char) <= _HEADER_LINES:
                    spans.append(_Span(ent.start_char, ent.end_char, "name"))
        spans += _first_line_name(text)
        return spans


def _Span_to_item(span: _Span, text: str) -> PIIItem:
    raw = text[span.start : span.end]
    return PIIItem(type=span.pii_type, detected=_mask(raw), action="redacted")


def _mask(value: str) -> str:
    """Obfuscate a captured value for the privacy report (never raw PII)."""
    value = " ".join(value.split())
    if not value:
        return "\u2026"
    if "@" in value:  # emails
        local, _, domain = value.partition("@")
        return f"{local[:2]}\u2026@{domain}"
    if value[-1].isdigit():  # IDs / phones
        return f"{value[:2]}\u2026{value[-1]}"
    words = value.split()
    return f"{words[0][:1]}\u2026" if len(words) == 1 else f"{words[0][:1]}\u2026{words[-1][:1]}"
    def overlap(self, other: "_Span") -> bool:
        return self.start < other.end and other.start < self.end