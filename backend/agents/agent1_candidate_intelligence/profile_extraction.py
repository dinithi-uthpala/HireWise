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
# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
def extract_skills(sections: dict[str, str], full_text: str) -> tuple[list[str], list[str]]:
    """Technical skills prefer the skills section; fall back to full text."""
    target = next((sections[key] for key in sections if key in _SKILL_ALIASES), "") or full_text
    return find_skills_in_text(target), find_soft_skills_in_text(target)


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
_QUAL_ORDER: list[tuple[str, str]] = [
    ("phd", "PhD"), ("doctorate", "PhD"),
    ("master", "Master"), ("mba", "Master"), ("msc", "Master"), ("meng", "Master"),
    ("bachelor", "Bachelor"), ("bsc", "Bachelor"), ("beng", "Bachelor"),
    ("hnd", "HND"), ("hnc", "HNC"),
    ("diploma", "Diploma"), ("foundation", "Foundation"),
]


def extract_education(sections: dict[str, str]) -> list[EducationEntry]:
    block = next((sections[key] for key in sections if key in _EDU_ALIASES), "")
    if not block:
        return []
    entries: list[EducationEntry] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        degree_line, level, subject = _parse_degree_line(line)
        if degree_line:
            entries.append(EducationEntry(
                degree=degree_line,
                qualification_level=level,
                subject=subject,
            ))
    return entries


def _parse_degree_line(line: str) -> tuple[str, str, str]:
    """Return (degree_text, qualification_level, subject). Empty tuple if no degree."""
    cleaned = re.sub(r"^\s*[-•▪◦*]\s*", "", line)
    level = ""
    for pattern, label in _QUAL_ORDER:
        if re.search(r"(?i)\b" + re.escape(pattern) + r"\b", cleaned):
            level = label
            break
    if not level:
        return ("", "", "")
    subject = ""
    subj = re.search(r"(?i)\bin\s+([A-Z][A-Za-z &'-]{2,40})", cleaned)
    if subj:
        subject = subj.group(1).strip()
    return cleaned, level, subject
# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------
_CERT_START_RE = re.compile(
    r"(?i)^\s*[-•▪◦*]?\s*"
    r"(certified|certificate\s+in|certification\s+in|professional\s+certificate|"
    r"google\s+certificate|ibm\s+certificate|microsoft\s+certified|aws\s+certified|"
    r"coursera|udemy|accredited|licen[cs]e\s+in)"
)


def extract_certifications(sections: dict[str, str]) -> list[str]:
    block = next((sections[key] for key in sections if key in _CERT_ALIASES), "")
    out: list[str] = []
    if not block:
        return out
    for line in block.splitlines():
        if _CERT_START_RE.match(line):
            cert = _CERT_START_RE.sub("", line).strip().strip(".,;")
            if cert and cert.lower() not in {c.lower() for c in out}:
                out.append(cert)
    return out


# ---------------------------------------------------------------------------
# Work experience
# ---------------------------------------------------------------------------
_JOB_HINT_RE = re.compile(
    r"(?i)\b(data\s*analyst|data\s*scientist|business\s*analyst|analyst|"
    r"software\s*engineer|developer|web\s*developer|intern(?:ship)?|"
    r"junior\s*developer|associate|executive|manager|consultant|"
    r"machine\s*learning\s*engineer|database\s*administrator|qa\s*engineer)\b"
)


def extract_experience(sections: dict[str, str]) -> list[ExperienceEntry]:
    block = next((sections[key] for key in sections if key in _EXP_ALIASES), "")
    if not block:
        return []
    entries: list[ExperienceEntry] = []
    current: ExperienceEntry | None = None
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _DATE_RANGE_RE.search(line)
        if m:
            if current is not None:
# ---------------------------------------------------------------------------
# Job titles / employers / projects / summary
# ---------------------------------------------------------------------------
def extract_job_titles(experience: list[ExperienceEntry]) -> list[str]:
    seen: list[str] = []
    for entry in experience:
        role = entry.role
        if role and role.lower() not in {r.lower() for r in seen}:
            seen.append(role)
    return seen


def extract_employers(experience: list[ExperienceEntry]) -> list[str]:
    seen: list[str] = []
    for entry in experience:
        employer = entry.employer
        if employer and employer.lower() not in {e.lower() for e in seen}:
            seen.append(employer)
    return seen


def extract_projects(sections: dict[str, str]) -> list[str]:
    block = next((sections[key] for key in sections if key in _PROJ_ALIASES), "")
    out: list[str] = []
    if not block:
        return out
    for line in block.splitlines():
        line = line.strip().lstrip("-•▪◦*").strip()
        if line and line.lower() not in {p.lower() for p in out}:
            out.append(line)
    return out[:10]


def extract_summary(sections: dict[str, str]) -> str:
    block = next((sections[key] for key in sections if key in _SUMMARY_ALIASES), "")
    if not block:
        return ""
    return " ".join(block.split())[:300]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def extract_profile(candidate_id: str, redacted_text: str) -> CandidateProfile:
    """Build an anonymous, job-relevant profile from PII-redacted CV text."""
    sections = split_sections(redacted_text)
    technical_skills, soft_skills = extract_skills(sections, redacted_text)
    education = extract_education(sections)
    experience = extract_experience(sections)
    total_months = sum(entry.months for entry in experience)

    return CandidateProfile(
        candidate_id=candidate_id,
        technical_skills=technical_skills,
        soft_skills=soft_skills,
        job_titles=extract_job_titles(experience),
        employers=extract_employers(experience),
        education=education,
        certifications=extract_certifications(sections),
        projects=extract_projects(sections),
        experience_entries=experience,
        total_experience_years=round(total_months / 12.0, 2),
        summary=extract_summary(sections),
    )
                entries.append(current)  # previous entry finished
            current = ExperienceEntry(
                role=_role_from_line(line, m),
                employer=_employer_from_line(line, m),
                start=m.group("start").strip(),
                end=m.group("end").strip(),
                months=range_months(m.group("start"), m.group("end")),
                summary=line,
            )
        elif current is not None and len(line) > 3:
            current.summary = f"{current.summary} {line}".strip()
            if not current.role:
                hint = _JOB_HINT_RE.search(line)
                if hint:
                    current.role = hint.group(1)
    if current is not None:
        entries.append(current)
    return [e for e in entries if e.months > 0 or e.role or e.employer]


def _role_from_line(line: str, m: re.Match) -> str:
    before = line[: m.start()].strip(" -–—|,;:")
    hint = _JOB_HINT_RE.search(before)
    if hint:
        return hint.group(1)
    return re.sub(r"^[-•▪◦*]\s*", "", before).strip()


def _employer_from_line(line: str, m: re.Match) -> str:
    after = line[m.end() : m.end() + 60].strip(" -–—|,;:")
    if not after:
        return ""
    return re.split(r"[,;|]", after, maxsplit=1)[0].strip()