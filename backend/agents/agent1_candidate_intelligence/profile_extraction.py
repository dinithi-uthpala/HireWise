"""Structured candidate-profile extraction (Agent 1).

Parses the *PII-redacted* CV text into a job-relevant, anonymous
:class:`CandidateProfile` for Agent 2. Nothing here reads identity data.

Pipeline (section-aware, deterministic):
    - technical / soft skills     via the shared skill taxonomy
    - education                   degree + qualification-level regex
    - certifications              "Certified ..." / "Certificate in ..." lines
    - work experience             date-range lines grouped into entries
    - job titles / employers      derived from experience entries
    - total experience            summed from date ranges (monthly precision)
"""
from __future__ import annotations

import re
from datetime import datetime

from backend.ir.skill_taxonomy import find_skills_in_text, find_soft_skills_in_text
from backend.schemas import CandidateProfile, EducationEntry, ExperienceEntry

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_MONTH_WORDS = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)

# A single date token: "Jan 2021" | "2021" | "01/2021" | "2021-01"
_DATE_TOKEN_RE = re.compile(
    r"(?:" + _MONTH_WORDS + r"[\s./-])?(?:19|20)\d{2}", re.IGNORECASE
)

# Date range: "Jan 2021 - Present" | "2020 – 2021" | "Mar 2020 to Present"
_DATE_RANGE_RE = re.compile(
    r"(?i)(?P<start>(?:" + _MONTH_WORDS + r"[\s./-])?(?:19|20)\d{2})"
    r"\s*[-–—to]+\s*(?P<end>present|now|current|(?:" + _MONTH_WORDS + r"[\s./-])?(?:19|20)\d{2})"
)

_PRESENT_TOKENS = {"present", "now", "current"}


def parse_smart_date(token: str) -> tuple[int, int] | None:
    """Parse a date token -> (year, month) with month 0 for year-only input."""
    m = _DATE_TOKEN_RE.search(token.strip().strip(".,;"))
    if not m:
        return None
    text = m.group(0)
    year = int(re.search(r"(19|20)\d{2}", text).group(0))
    month = 0
    mo = re.search(r"(?i)([a-z]+)", text)
    if mo and mo.group(1).lower()[:3] in _MONTHS:
        month = _MONTHS[mo.group(1).lower()[:3]]
# ---------------------------------------------------------------------------
# Section headings (case-insensitive, line-start)
# ---------------------------------------------------------------------------
_SECTION_HEADINGS = re.compile(
    r"(?im)^\s*(?:#+\s*|[-•▪◦*]\s*)?"
    r"(?P<title>education|academic\s*(?:background|qualifications|history)?|"
    r"experience|work\s*experience|employment(?:\s*history)?|career|"
    r"skills|technical\s*skills|professional\s*skills|core\s*skills|"
    r"projects?|project\s*experience|key\s*projects|academic\s*projects|"
    r"certifications?|certificates?|licen[cs]es?|"
    r"summary|profile|career\s*objective|objective|about\s*me)"
    r"(?:\s*:|\s*$)"
)

_SKILL_ALIASES = {"skills", "technical skills", "professional skills", "core skills"}
_EDU_ALIASES = {"education", "academic background", "academic qualifications", "academic history"}
_EXP_ALIASES = {"experience", "work experience", "employment", "employment history", "career"}
_PROJ_ALIASES = {"projects", "project", "project experience", "key projects", "academic projects"}
_CERT_ALIASES = {"certifications", "certification", "certificates", "certificate", "licenses", "licences", "license", "licence"}
_SUMMARY_ALIASES = {"summary", "profile", "career objective", "objective", "about me"}


def split_sections(text: str) -> dict[str, str]:
    """Split redacted CV text into named sections by heading keywords.

    Returns a mapping of normalized-section-name -> raw block text.
    Lines that belong to no known section (usually the header) land under
    the ``__head`` pseudo-key.
    """
    sections: dict[str, list[str]] = {"__head": []}
    current = "__head"
    for line in text.splitlines():
        m = _SECTION_HEADINGS.match(line)
        if m:
            current = m.group("title").strip().lower()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: re.sub(r"\n{2,}", "\n", "\n".join(lines)).strip("\n")
            for key, lines in sections.items()}
    return (year, month)


def range_months(start_token: str, end_token: str) -> float:
    """Estimate months spanned by a date range (month granularity)."""
    start = parse_smart_date(start_token)
    if start is None:
        return 0.0
    if end_token.strip().lower() in _PRESENT_TOKENS:
        end = (datetime.now().year, datetime.now().month)
    else:
        end = parse_smart_date(end_token) or start
    return max(0.0, float((end[0] - start[0]) * 12 + (end[1] - start[1]) + 1))