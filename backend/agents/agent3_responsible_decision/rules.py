"""Agent 3 - deterministic Responsible-AI rules.

Everything here is plain Python with NO LLM, so every decision can be
explained and audited line by line.

Functions:
    check_privacy(...)                independent re-check for leaked personal data
    derive_matching_confidence(...)   confidence in Agent 2's match (Agent 2 gives none)
    build_flags(...)                  human-review rules -> list of RiskFlag
    choose_recommendation(...)        score + flags -> cautious label (never "Rejected")
"""
from __future__ import annotations

import re

from backend.schemas import (
    ExtractionResult,
    MatchResult,
    PrivacyCheck,
    ReviewThresholds,
    RiskFlag,
)

# --- cautious labels (from the HireWise design document) --------------------
STRONG = "STRONG_MATCH"
POTENTIAL = "POTENTIAL_MATCH"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
MANUAL = "MANUAL_REVIEW"

LABELS = {
    STRONG: "Strong match - recruiter review required",
    POTENTIAL: "Potential match - recruiter review required",
    INSUFFICIENT: "Insufficient job-related evidence - recruiter review required",
    MANUAL: "Manual review required - do not rely on score alone",
}

# --- privacy patterns -------------------------------------------------------
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_CANDIDATE = re.compile(r"\(?\+?\d[\d\s().-]{6,}\d\)?")
# Sri Lankan NIC: 9 digits + V/X (old) or 12 digits (new)
_NIC = re.compile(r"(?<!\d)(?:\d{9}[VvXx]|\d{12})(?!\d)")
# Personal attributes that must never influence (or appear in) scoring evidence
_PROHIBITED = re.compile(
    r"\b(gender|male|female|religion|religious|marital|married|unmarried|"
    r"ethnicity|ethnic|nationality|disability|disabled|date of birth|dob|"
    r"years old|pregnan\w*)\b",
    re.IGNORECASE,
)


def _has_phone(text: str) -> bool:
    """A phone number needs >= 9 digits, so year ranges like '2019 - 2021' pass."""
    for m in _PHONE_CANDIDATE.finditer(text):
        if sum(ch.isdigit() for ch in m.group()) >= 9:
            return True
    return False


def _pii_kinds(text: str) -> list[str]:
    kinds = []
    if _EMAIL.search(text):
        kinds.append("email address")
    if _has_phone(text):
        kinds.append("phone number")
    if _NIC.search(text):
        kinds.append("national ID number")
    return kinds


def _profile_texts(extraction: ExtractionResult) -> list[str]:
    """All free-text parts of the anonymous profile (institution is excluded on
    purpose: Agent 1 keeps it for reference only)."""
    p = extraction.profile
    texts = [p.summary]
    texts += p.technical_skills + p.soft_skills + p.job_titles + p.employers
    texts += p.certifications + p.projects
    for e in p.experience_entries:
        texts += [e.role, e.employer, e.start, e.end, e.summary]
    for ed in p.education:
        texts += [ed.degree, ed.qualification_level, ed.subject]
    return [t for t in texts if t]


def _match_texts(match: MatchResult) -> list[str]:
    """Every sentence Agent 2 produced to justify its score."""
    ev = match.score_evidence
    texts = [
        ev.mandatory_skills.evidence,
        ev.preferred_skills.evidence,
        ev.experience.evidence,
        ev.education.evidence,
        ev.education.required_education,
        match.responsibility_evidence.evidence,
        match.certification_evidence.evidence,
    ]
    texts += ev.education.candidate_education
    texts += [g.reason for g in match.skill_gaps]
    for u in match.uncertain_matches:
        texts += [u.reason, u.candidate_evidence]
    texts += match.warnings
    return [t for t in texts if t]


# ---------------------------------------------------------------------------
# 1. Privacy check
# ---------------------------------------------------------------------------
def check_privacy(extraction: ExtractionResult, match: MatchResult) -> PrivacyCheck:
    """Second, independent privacy check (defence in depth after Agent 1).

    Violations describe WHAT was found and WHERE, never the value itself, so
    the audit log stays free of personal data.
    """
    checked = [
        "No email, phone or national-ID pattern in the anonymous profile",
        "No email, phone or national-ID pattern in the redacted CV text",
        "University/institution names not used in scoring evidence",
        "No prohibited personal attribute mentioned in scoring evidence",
    ]
    violations: list[str] = []

    for text in _profile_texts(extraction):
        for kind in _pii_kinds(text):
            violations.append(f"Possible {kind} found in the anonymous profile")
    for kind in _pii_kinds(extraction.pii.redacted_text or ""):
        violations.append(f"Possible {kind} found in the redacted CV text")

    match_texts = _match_texts(match)
    lowered = [t.lower() for t in match_texts]
    for edu in extraction.profile.education:
        inst = (edu.institution or "").strip().lower()
        if len(inst) >= 3 and any(inst in t for t in lowered):
            violations.append("An institution name appears in the scoring evidence")
            break
    for text in match_texts:
        if _PROHIBITED.search(text):
            violations.append("A prohibited personal attribute is mentioned in the scoring evidence")
            break

    # de-duplicate, keep order
    violations = list(dict.fromkeys(violations))
    return PrivacyCheck(passed=not violations, checked_items=checked, violations=violations)


# ---------------------------------------------------------------------------
# 2. Matching confidence (derived, because Agent 2 does not provide one)
# ---------------------------------------------------------------------------
def derive_matching_confidence(match: MatchResult) -> float:
    """Simple, documented heuristic:
        start at 1.0
        - 0.10 for each uncertain match (max -0.50)
        - 0.15 if nothing was retrieved from the knowledge base
        - 0.15 if Agent 2 itself reported match_status == 'warning'
        0.0 when there is no usable score at all.
    """
    if match.match_status == "unavailable" or match.match_score is None:
        return 0.0
    conf = 1.0
    conf -= min(0.5, 0.10 * len(match.uncertain_matches))
    if not match.retrieval_evidence:
        conf -= 0.15
    if match.match_status == "warning":
        conf -= 0.15
    return round(max(0.0, min(1.0, conf)), 2)


# ---------------------------------------------------------------------------
# 3. Human-review rules -> risk flags
# ---------------------------------------------------------------------------
def _components_without_evidence(match: MatchResult) -> list[str]:
    """A component that earned points but has no written evidence."""
    b, ev = match.score_breakdown, match.score_evidence
    checks = [
        ("mandatory skills", b.mandatory_skills, ev.mandatory_skills.evidence),
        ("experience", b.experience, ev.experience.evidence),
        ("education/certifications", b.education, ev.education.evidence),
        ("preferred skills", b.preferred_skills, ev.preferred_skills.evidence),
    ]
    return [name for name, points, text in checks if points > 0 and not (text or "").strip()]


def build_flags(
    extraction: ExtractionResult,
    match: MatchResult,
    privacy: PrivacyCheck,
    matching_conf: float,
    th: ReviewThresholds,
) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    score = match.match_score

    if extraction.candidate_id != match.candidate_id:
        flags.append(RiskFlag(
            code="CANDIDATE_ID_MISMATCH", severity="critical", forces_manual_review=True,
            message="The extraction result and the match result belong to different candidate IDs.",
        ))

    if not privacy.passed:
        flags.append(RiskFlag(
            code="PRIVACY_CHECK_FAILED", severity="critical", forces_manual_review=True,
            message="Possible personal data was found where it should not be. " + "; ".join(privacy.violations),
        ))

    if extraction.parse_status == "failed":
        flags.append(RiskFlag(
            code="PARSE_FAILED", severity="critical", forces_manual_review=True,
            message="The CV could not be read reliably. Please review the original CV.",
        ))
    elif extraction.parse_status == "low_confidence":
        flags.append(RiskFlag(
            code="LOW_QUALITY_PARSE", severity="warning", forces_manual_review=True,
            message="The CV was only partly readable, so some information may be missing.",
        ))

    if extraction.extraction_confidence < th.extraction_confidence_ok:
        flags.append(RiskFlag(
            code="LOW_EXTRACTION_CONFIDENCE", severity="warning", forces_manual_review=True,
            message=(f"Extraction confidence is {extraction.extraction_confidence:.0%}, below the "
                     f"{th.extraction_confidence_ok:.0%} threshold."),
        ))

    if match.match_status == "unavailable" or score is None:
        flags.append(RiskFlag(
            code="MATCH_UNAVAILABLE", severity="critical", forces_manual_review=True,
            message="No reliable score could be produced for this candidate.",
        ))
    elif matching_conf < th.matching_confidence_ok:
        flags.append(RiskFlag(
            code="LOW_MATCHING_CONFIDENCE", severity="warning", forces_manual_review=True,
            message=(f"Matching confidence is {matching_conf:.0%}, below the "
                     f"{th.matching_confidence_ok:.0%} threshold."),
        ))

    missing_mandatory = [g.skill for g in match.skill_gaps if g.category == "mandatory"]
    if missing_mandatory:
        flags.append(RiskFlag(
            code="MISSING_MANDATORY_SKILLS", severity="warning",
            message="Mandatory skills with no evidence in the CV: " + ", ".join(missing_mandatory) + ".",
        ))

    if match.uncertain_matches:
        flags.append(RiskFlag(
            code="UNCERTAIN_MATCHES", severity="warning",
            message=(f"{len(match.uncertain_matches)} requirement(s) could not be confirmed. "
                     "They were not assumed to be met."),
        ))

    no_evidence = _components_without_evidence(match)
    if no_evidence:
        flags.append(RiskFlag(
            code="MISSING_SCORE_EVIDENCE", severity="warning",
            message="Points were given without written evidence for: " + ", ".join(no_evidence) + ".",
        ))

    if score is not None:
        b = match.score_breakdown
        total = b.mandatory_skills + b.experience + b.education + b.preferred_skills
        diff = abs(total - score)
        if diff > 5:
            flags.append(RiskFlag(
                code="SCORE_INCONSISTENT", severity="critical", forces_manual_review=True,
                message=f"The component points add up to {total:.1f} but the final score is {score:.1f}.",
            ))
        elif diff > 1:
            flags.append(RiskFlag(
                code="SCORE_BREAKDOWN_MISMATCH", severity="warning",
                message=f"The component points add up to {total:.1f} but the final score is {score:.1f}.",
            ))
        if (abs(score - th.strong_match_min) <= th.borderline_margin
                or abs(score - th.potential_match_min) <= th.borderline_margin):
            flags.append(RiskFlag(
                code="BORDERLINE_SCORE", severity="warning",
                message=f"The score ({score:.1f}) is close to a recommendation boundary.",
            ))

    return flags


# ---------------------------------------------------------------------------
# 4. Recommendation (cautious label - never "Rejected")
# ---------------------------------------------------------------------------
def choose_recommendation(score: float | None, flags: list[RiskFlag], th: ReviewThresholds) -> tuple[str, str]:
    """Return (code, display label)."""
    if score is None or any(f.forces_manual_review for f in flags):
        code = MANUAL
    elif score < th.potential_match_min or any(f.code == "MISSING_SCORE_EVIDENCE" for f in flags):
        code = INSUFFICIENT
    elif score >= th.strong_match_min and all(f.severity == "info" for f in flags):
        code = STRONG            # "80-100, no risk flags"
    else:
        code = POTENTIAL
    return code, LABELS[code]
