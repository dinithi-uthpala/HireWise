"""Deterministic job-requirement extraction for Agent 2.

This module converts a job title and description into the shared
:class:`JobRequirement` contract. It deliberately uses no LLM: skills come
from the shared taxonomy, while experience and education use small,
auditable regular-expression rules.
"""
from __future__ import annotations

import re

from backend.ir.skill_taxonomy import SKILL_SYNONYMS, find_skills_in_text, normalize_skill
from backend.schemas import JobRequirement
from backend.security.sanitize import strip_prompt_injections


_MANDATORY_CONTEXT = re.compile(
    r"\b(?:required|must[- ]have|mandatory|essential)\b", re.IGNORECASE
)
_PREFERRED_CONTEXT = re.compile(
    r"\b(?:preferred|nice[- ]to[- ]have|good[- ]to[- ]have|bonus|advantage)\b",
    re.IGNORECASE,
)
_EXPERIENCE_PATTERNS = (
    re.compile(
        r"\b(?:at\s+least|minimum\s+of|min(?:imum)?)\s*"
        r"(?P<years>\d+(?:\.\d+)?)\s*(?:\+\s*)?years?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<years>\d+(?:\.\d+)?)\s*\+?\s*years?\s*(?:of\s+)?"
        r"(?:relevant\s+|professional\s+)?experience\b",
        re.IGNORECASE,
    ),
)
_EDUCATION_LEVELS = (
    ("phd", re.compile(r"\b(?:ph\.?d\.?|doctorate|doctoral)\b", re.IGNORECASE)),
    ("master", re.compile(r"\b(?:master(?:'s)?|msc|meng|mba)\b", re.IGNORECASE)),
    ("bachelor", re.compile(r"\b(?:bachelor(?:'s)?|bsc|beng)\b", re.IGNORECASE)),
    ("diploma", re.compile(r"\b(?:diploma|higher national diploma|hnd|hnc)\b", re.IGNORECASE)),
)
_RESPONSIBILITY_HEADINGS = re.compile(
    r"(?i)^\s*(?:(?:key\s+)?responsibilit(?:y|ies)|duties|key\s+tasks)\s*:"
)
_CERTIFICATION_HEADINGS = re.compile(
    r"(?i)^\s*(?:required\s+)?(?:certifications?|licenses?|licences?)\s*:"
)
_CERTIFICATION_LINE = re.compile(
    r"(?i)\b(?:certification|certificate|certified|license|licence)\b"
)
_REQUIREMENT_SECTION_HEADINGS = re.compile(
    r"(?i)^\s*(?:(?:required|mandatory|preferred|minimum|key)\s+)?"
    r"(?:skills?|education|qualifications?|experience|responsibilit(?:y|ies)|"
    r"duties|tasks|certifications?|licenses?|licences?)\s*:"
)
_CERTIFICATION_PROSE_START = re.compile(
    r"(?i)^\s*(?:candidates?|applicants?|this\s+role|the\s+role|please\s+|"
    r"must\s+|should\s+|responsibilities?\b|experience\b)"
)
_CERTIFICATION_PROVIDER = re.compile(
    r"(?i)\b(?:aws|amazon|microsoft|azure|google|gcp|ibm|cisco|oracle|"
    r"comptia|salesforce|kubernetes|pmi|isc2)\b"
)


def extract_job_requirements(
    title: str,
    description: str,
    job_id: str = "",
) -> tuple[JobRequirement, list[str]]:
    """Extract normalized requirements and warnings from a job description.

    Returns the shared ``JobRequirement`` model together with warnings about
    information that was not found reliably. Skills without an explicit
    preferred marker are treated as mandatory, which is conservative for
    first-stage recruitment matching.
    """
    clean_title = strip_prompt_injections(title).strip()
    clean_description = strip_prompt_injections(description)
    skills = _extract_skills(clean_description)
    mandatory_skills, preferred_skills = _classify_skills(clean_description, skills)
    minimum_experience_years = _extract_experience_years(clean_description)
    required_education_level = _extract_education_level(clean_description)
    responsibilities = _extract_responsibilities(clean_description)
    required_certifications = _extract_certifications(clean_description)

    warnings: list[str] = []
    if not skills:
        warnings.append("No skills were identified against the shared skill taxonomy.")
    if minimum_experience_years == 0.0:
        warnings.append("Minimum required experience could not be determined.")
    if not required_education_level:
        warnings.append("Required education level could not be determined.")

    requirements = JobRequirement(
        job_id=job_id,
        title=clean_title,
        description=clean_description,
        mandatory_skills=mandatory_skills,
        preferred_skills=preferred_skills,
        minimum_experience_years=minimum_experience_years,
        required_education_level=required_education_level,
        responsibilities=responsibilities,
        required_certifications=required_certifications,
    )
    return requirements, warnings


def _extract_skills(description: str) -> list[str]:
    """Find taxonomy skills and normalize them to canonical names."""
    found = find_skills_in_text(description)
    normalized: list[str] = []
    for skill in found:
        canonical = normalize_skill(skill)
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def _classify_skills(description: str, skills: list[str]) -> tuple[list[str], list[str]]:
    """Classify skills using markers in their containing clauses."""
    mandatory: list[str] = []
    preferred: list[str] = []
    clauses = _requirement_clauses(description)

    for skill in skills:
        clause = _skill_clause(clauses, skill)
        if _PREFERRED_CONTEXT.search(clause) and not _MANDATORY_CONTEXT.search(clause):
            preferred.append(skill)
        else:
            mandatory.append(skill)
    return mandatory, preferred


def _requirement_clauses(description: str) -> list[str]:
    """Split requirements at line and sentence boundaries."""
    return [
        clause.strip().lower()
        for clause in re.split(r"\n+|(?<=[.!?;])\s+", description)
        if clause.strip()
    ]


def _skill_clause(clauses: list[str], canonical_skill: str) -> str:
    """Return the clause containing a canonical skill or one of its aliases."""
    forms = SKILL_SYNONYMS.get(canonical_skill, {canonical_skill})
    skill_forms = forms | {canonical_skill}
    for clause in clauses:
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(form.lower())}(?![a-z0-9])", clause)
            for form in skill_forms
        ):
            return clause
    return ""


def _extract_experience_years(description: str) -> float:
    """Extract the first explicit minimum or relevant experience value."""
    for pattern in _EXPERIENCE_PATTERNS:
        match = pattern.search(description)
        if match:
            return float(match.group("years"))
    return 0.0


def _extract_education_level(description: str) -> str:
    """Return the highest explicitly requested education level found."""
    for level, pattern in _EDUCATION_LEVELS:
        if pattern.search(description):
            return level
    return ""


def _extract_responsibilities(description: str) -> list[str]:
    """Extract explicit responsibility lines without inventing duties."""
    lines = description.splitlines()
    output: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_section:
                in_section = False
            continue
        if _RESPONSIBILITY_HEADINGS.match(stripped):
            in_section = True
            remainder = re.sub(_RESPONSIBILITY_HEADINGS, "", stripped).strip(" :-")
            if remainder:
                _append_items(output, remainder)
            continue
        if in_section and _CERTIFICATION_HEADINGS.match(stripped):
            in_section = False
            continue
        if in_section:
            _append_items(output, stripped)
    return output[:20]


def _extract_certifications(description: str) -> list[str]:
    """Extract certification names from explicit certification sections."""
    lines = description.splitlines()
    output: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_section:
                in_section = False
            continue
        if _CERTIFICATION_HEADINGS.match(stripped):
            in_section = True
            remainder = re.sub(_CERTIFICATION_HEADINGS, "", stripped).strip(" :-")
            if remainder:
                _append_certification_items(output, remainder)
            continue
        if in_section:
            if _REQUIREMENT_SECTION_HEADINGS.match(stripped):
                in_section = False
                continue
            if _CERTIFICATION_PROSE_START.match(stripped):
                in_section = False
                continue
            if stripped:
                _append_certification_items(output, stripped)
    return output[:20]


def _append_items(output: list[str], line: str) -> None:
    """Append cleaned bullet/semicolon items without duplicates."""
    for item in re.split(r"[;|]", line):
        cleaned = re.sub(r"^[-*•▪◦]\s*", "", item).strip(" .,:")
        if cleaned and cleaned.lower() not in {value.lower() for value in output}:
            output.append(cleaned)


def _append_certification_items(output: list[str], line: str) -> None:
    """Split certification lists without splitting ordinary name commas."""
    for item in re.split(r"[;|]", line):
        cleaned = item.strip(" .,:;")
        if not cleaned:
            continue
        comma_parts = [part.strip() for part in cleaned.split(",")]
        if len(comma_parts) > 1 and all(
            _CERTIFICATION_PROVIDER.search(part) for part in comma_parts[1:]
        ):
            parts = comma_parts
        else:
            parts = [cleaned]
        for part in parts:
            value = re.sub(r"^[-*•▪◦]\s*", "", part).strip(" .,:;")
            if value and value.lower() not in {entry.lower() for entry in output}:
                output.append(value)
