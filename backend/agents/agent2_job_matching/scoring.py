"""Deterministic and explainable candidate-to-job scoring for Agent 2."""
from __future__ import annotations

import re

from backend.config import get_settings
from backend.ir.skill_taxonomy import normalize_skill
from backend.schemas import (
    CandidateProfile,
    JobRequirement,
    MatchResult,
    EducationScoreEvidence,
    ScoreBreakdown,
    ScoreEvidence,
    SkillScoreEvidence,
    SkillGap,
    ExperienceScoreEvidence,
    RequirementMatchEvidence,
    UncertainMatch,
)


_EDUCATION_LEVELS = {
    "diploma": 1,
    "hnc": 1,
    "hnd": 1,
    "bachelor": 2,
    "bsc": 2,
    "beng": 2,
    "master": 3,
    "msc": 3,
    "meng": 3,
    "mba": 3,
    "phd": 4,
    "doctorate": 4,
}


def score_candidate(candidate: CandidateProfile, job: JobRequirement) -> MatchResult:
    """Score one anonymous candidate profile against one job requirement.

    The result uses four component scores from 0 to 100. Their weighted sum
    uses the Agent 2 weights in ``backend.config.Settings``.
    """
    mandatory_skills = _normalized_skills(job.mandatory_skills)
    preferred_skills = _normalized_skills(job.preferred_skills)

    if (
        not mandatory_skills
        and not preferred_skills
        and not job.minimum_experience_years
        and not job.required_education_level.strip()
        and not job.required_certifications
        and not job.responsibilities
    ):
        return MatchResult(
            candidate_id=candidate.candidate_id,
            job_id=job.job_id,
            parse_status="ok",
            match_status="unavailable",
            extraction_confidence=1.0,
            match_score=None,
            warnings=["Matching is unavailable because no measurable job requirements were identified."],
        )

    candidate_skills = _normalized_candidate_skills(candidate)

    matched_mandatory = [skill for skill in mandatory_skills if skill in candidate_skills]
    matched_preferred = [skill for skill in preferred_skills if skill in candidate_skills]
    skill_gaps = _build_skill_gaps(mandatory_skills, preferred_skills, candidate_skills)

    settings = get_settings()
    mandatory_percentage = _percentage(len(matched_mandatory), len(mandatory_skills))
    preferred_percentage = _percentage(len(matched_preferred), len(preferred_skills))
    experience_percentage = _experience_score(
            candidate.total_experience_years,
            job.minimum_experience_years,
    )
    education_percentage = _education_score(candidate, job.required_education_level)
    candidate_education = _candidate_education_labels(candidate)
    responsibility_evidence = _match_responsibilities(candidate, job.responsibilities)
    certification_evidence = _match_certifications(
        candidate.certifications, job.required_certifications
    )
    uncertain_matches = _build_uncertain_matches(
        candidate,
        job,
        matched_mandatory,
        matched_preferred,
        responsibility_evidence,
        certification_evidence,
    )

    education_required = bool(job.required_education_level.strip())
    certifications_required = bool(job.required_certifications)
    education_share, certification_share = _education_certification_shares(
        education_required,
        certifications_required,
        settings.weight_education,
    )
    certification_percentage = _percentage(
        len(certification_evidence.matched), len(job.required_certifications)
    )
    education_contribution = round(education_percentage * education_share, 2)
    certification_contribution = round(certification_percentage * certification_share, 2)
    if not education_required and not certifications_required:
        combined_contribution = round(settings.weight_education * 100.0, 2)
        education_evidence_text = (
            "No education or certification requirements specified; full component credit awarded."
        )
    else:
        combined_contribution = round(
            education_contribution + certification_contribution, 2
        )
        education_evidence_text = _combined_education_certification_evidence(
            education_required,
            certifications_required,
            education_contribution,
            certification_contribution,
            combined_contribution,
        )

    missing_mandatory = [
        skill for skill in mandatory_skills if skill not in candidate_skills
    ]
    missing_preferred = [
        skill for skill in preferred_skills if skill not in candidate_skills
    ]

    breakdown = ScoreBreakdown(
        mandatory_skills=round(mandatory_percentage * settings.weight_mandatory_skills, 2),
        preferred_skills=round(preferred_percentage * settings.weight_preferred_skills, 2),
        experience=round(experience_percentage * settings.weight_experience, 2),
        education=combined_contribution,
    )

    score_evidence = ScoreEvidence(
        mandatory_skills=SkillScoreEvidence(
            score=breakdown.mandatory_skills,
            matched=matched_mandatory,
            missing=missing_mandatory,
            evidence=_skill_evidence(
                len(matched_mandatory), len(mandatory_skills), "mandatory"
            ),
        ),
        preferred_skills=SkillScoreEvidence(
            score=breakdown.preferred_skills,
            matched=matched_preferred,
            missing=missing_preferred,
            evidence=_skill_evidence(
                len(matched_preferred), len(preferred_skills), "preferred"
            ),
        ),
        experience=ExperienceScoreEvidence(
            score=breakdown.experience,
            candidate_years=candidate.total_experience_years,
            required_years=job.minimum_experience_years,
            evidence=_experience_evidence(
                candidate.total_experience_years, job.minimum_experience_years
            ),
        ),
        education=EducationScoreEvidence(
            score=breakdown.education,
            candidate_education=candidate_education,
            required_education=job.required_education_level,
            education_match_status=_education_match_status(
                education_percentage, education_required
            ),
            education_contribution=education_contribution,
            required_certifications=job.required_certifications,
            matched_certifications=certification_evidence.matched,
            missing_certifications=certification_evidence.missing,
            certification_match_status=_certification_match_status(
                certification_evidence, certifications_required
            ),
            certification_contribution=certification_contribution,
            total_combined_contribution=combined_contribution,
            evidence=education_evidence_text,
        ),
    )

    weighted_score = (
        breakdown.mandatory_skills
        + breakdown.experience
        + breakdown.education
        + breakdown.preferred_skills
    )

    warnings: list[str] = []
    if missing_mandatory:
        warnings.append(f"Missing mandatory skills: {', '.join(missing_mandatory)}")

    return MatchResult(
        candidate_id=candidate.candidate_id,
        job_id=job.job_id,
        parse_status="ok",
        match_status="scored",
        extraction_confidence=1.0,
        match_score=round(max(0.0, min(100.0, weighted_score)), 2),
        score_breakdown=breakdown,
        matched_mandatory_skills=matched_mandatory,
        matched_preferred_skills=matched_preferred,
        skill_gaps=skill_gaps,
        score_evidence=score_evidence,
        responsibility_evidence=responsibility_evidence,
        certification_evidence=certification_evidence,
        uncertain_matches=uncertain_matches,
        warnings=warnings,
    )


_AMBIGUOUS_EVIDENCE_RE = re.compile(
    r"\b(?:worked with|familiar with|exposure to|experience with|"
    r"used various|data tools?|related tools?|similar tools?|some knowledge)\b",
    re.IGNORECASE,
)


def _build_uncertain_matches(
    candidate: CandidateProfile,
    job: JobRequirement,
    matched_mandatory: list[str],
    matched_preferred: list[str],
    responsibility_evidence: RequirementMatchEvidence,
    certification_evidence: RequirementMatchEvidence,
) -> list[UncertainMatch]:
    """Flag only ambiguous candidate evidence without changing the score."""
    uncertain: list[UncertainMatch] = []
    candidate_text = _candidate_evidence_text(candidate)

    missing_skills = [
        skill for skill in job.mandatory_skills + job.preferred_skills
        if skill not in matched_mandatory and skill not in matched_preferred
    ]
    ambiguous_skill = _ambiguous_excerpt(candidate_text)
    if ambiguous_skill:
        for skill in missing_skills:
            uncertain.append(UncertainMatch(
                requirement_type="skill",
                requirement=skill,
                reason="Candidate evidence refers to related tools without naming the required skill.",
                candidate_evidence=ambiguous_skill,
            ))

    if job.minimum_experience_years > 0 and not candidate.experience_entries:
        if candidate.total_experience_years > 0 or re.search(
            r"\b(?:experience|worked|project)\b", candidate_text, re.IGNORECASE
        ):
            uncertain.append(UncertainMatch(
                requirement_type="experience",
                requirement=f"{job.minimum_experience_years:g} years relevant experience",
                reason="Experience duration or relevance could not be confirmed from dated experience entries.",
                candidate_evidence=_evidence_excerpt(candidate_text, "experience"),
            ))

    required_education = job.required_education_level.strip()
    if required_education and candidate.education:
        if max(
            (_education_rank(entry.qualification_level or entry.degree)
             for entry in candidate.education),
            default=0,
        ) == 0:
            uncertain.append(UncertainMatch(
                requirement_type="education",
                requirement=required_education,
                reason="Candidate qualification is present but cannot be mapped to a recognized education level.",
                candidate_evidence="; ".join(
                    entry.degree or entry.qualification_level
                    for entry in candidate.education
                ),
            ))

    for certification in certification_evidence.missing:
        if candidate.certifications:
            uncertain.append(UncertainMatch(
                requirement_type="certification",
                requirement=certification,
                reason="Candidate lists certifications, but none clearly matches this requirement.",
                candidate_evidence="; ".join(candidate.certifications),
            ))

    candidate_tokens = set(_tokens(candidate_text))
    for responsibility in responsibility_evidence.missing:
        responsibility_tokens = _phrase_tokens(responsibility)
        overlap = responsibility_tokens & candidate_tokens
        if overlap and overlap != responsibility_tokens:
            uncertain.append(UncertainMatch(
                requirement_type="responsibility",
                requirement=responsibility,
                reason="Candidate evidence partially overlaps the responsibility but does not establish the full duty.",
                candidate_evidence=_evidence_excerpt(candidate_text, sorted(overlap)[0]),
            ))

    return uncertain


def _candidate_evidence_text(candidate: CandidateProfile) -> str:
    """Collect anonymous evidence fields used for ambiguity checks."""
    return " ".join(
        part.strip()
        for part in [
            candidate.summary,
            *(entry.summary for entry in candidate.experience_entries),
            *candidate.projects,
        ]
        if part and part.strip()
    )


def _ambiguous_excerpt(text: str) -> str:
    match = _AMBIGUOUS_EVIDENCE_RE.search(text)
    if not match:
        return ""
    return _evidence_excerpt(text, match.group(0))


def _evidence_excerpt(text: str, marker: str) -> str:
    """Return a short exact excerpt from anonymous candidate evidence."""
    if not text:
        return ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if marker.lower() in sentence.lower():
            return sentence[:300]
    return text[:300]


def _education_certification_shares(
    education_required: bool,
    certifications_required: bool,
    component_weight: float,
) -> tuple[float, float]:
    """Split the fixed education/certification weight deterministically."""
    if education_required and certifications_required:
        share = component_weight / 2.0
        return share, share
    if education_required:
        return component_weight, 0.0
    if certifications_required:
        return 0.0, component_weight
    return 0.0, 0.0


def _education_match_status(score: float, required: bool) -> str:
    if not required:
        return "not_required"
    if score >= 100.0:
        return "matched"
    if score > 0.0:
        return "partial"
    return "missing"


def _certification_match_status(
    evidence: RequirementMatchEvidence,
    required: bool,
) -> str:
    if not required:
        return "not_required"
    if len(evidence.matched) == len(evidence.required):
        return "matched"
    if evidence.matched:
        return "partial"
    return "missing"


def _combined_education_certification_evidence(
    education_required: bool,
    certifications_required: bool,
    education_contribution: float,
    certification_contribution: float,
    combined_contribution: float,
) -> str:
    requirements: list[str] = []
    if education_required:
        requirements.append(
            f"education contribution {education_contribution:.2f}"
        )
    if certifications_required:
        requirements.append(
            f"certification contribution {certification_contribution:.2f}"
        )
    return (
        "Combined education/certification component uses a fixed equal split "
        "when both requirements are present; "
        + ", ".join(requirements)
        + f"; total contribution {combined_contribution:.2f} of 15.00."
    )


def _normalized_candidate_skills(candidate: CandidateProfile) -> set[str]:
    """Normalize technical and soft skills; ignore non-scoring profile fields."""
    return set(_normalized_skills(candidate.technical_skills + candidate.soft_skills))


def _normalized_skills(skills: list[str]) -> list[str]:
    """Normalize and deduplicate skills while preserving their input order."""
    normalized: list[str] = []
    for skill in skills:
        canonical = normalize_skill(skill)
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def _percentage(matched: int, required: int) -> float:
    """Return a bounded percentage; no listed requirements are fully satisfied."""
    if required == 0:
        return 100.0
    return round((matched / required) * 100.0, 2)


def _experience_score(candidate_years: float, required_years: float) -> float:
    """Award full credit when no minimum is specified, otherwise prorate."""
    if required_years <= 0:
        return 100.0
    return round(min(100.0, max(0.0, candidate_years / required_years * 100.0)), 2)


def _skill_evidence(matched: int, required: int, category: str) -> str:
    """Describe the exact skill-count calculation used for one component."""
    if required == 0:
        return f"No {category} skills specified; full component credit awarded."
    return f"Candidate matched {matched} of {required} {category} skills."


def _experience_evidence(candidate_years: float, required_years: float) -> str:
    """Describe the exact experience comparison used for scoring."""
    if required_years <= 0:
        return "No minimum experience specified; full component credit awarded."
    if candidate_years >= required_years:
        return "Candidate meets the minimum required experience."
    return "Candidate has less than the minimum required experience; partial credit awarded."


def _education_score(candidate: CandidateProfile, required_level: str) -> float:
    """Compare education levels without using institution names."""
    required = _education_rank(required_level)
    if required == 0:
        return 100.0

    candidate_rank = max(
        (_education_rank(entry.qualification_level or entry.degree) for entry in candidate.education),
        default=0,
    )
    if candidate_rank >= required:
        return 100.0
    if candidate_rank == 0:
        return 0.0
    return round(candidate_rank / required * 100.0, 2)


def _candidate_education_labels(candidate: CandidateProfile) -> list[str]:
    """Return qualification labels without exposing education institutions."""
    labels: list[str] = []
    for entry in candidate.education:
        label = (entry.qualification_level or entry.degree).strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def _match_responsibilities(
    candidate: CandidateProfile,
    responsibilities: list[str],
) -> RequirementMatchEvidence:
    """Match only explicit responsibility phrases in candidate evidence."""
    candidate_text = " ".join(
        [entry.summary for entry in candidate.experience_entries] + candidate.projects
    ).lower()
    matched = [
        responsibility for responsibility in responsibilities
        if _phrase_tokens(responsibility).issubset(set(_tokens(candidate_text)))
        and _phrase_tokens(responsibility)
    ]
    missing = [item for item in responsibilities if item not in matched]
    if not responsibilities:
        explanation = "No explicit job responsibilities were extracted."
    elif not candidate_text.strip():
        explanation = "No candidate responsibility evidence was available in experience summaries or projects."
    else:
        explanation = f"Candidate evidence matched {len(matched)} of {len(responsibilities)} responsibilities."
    return RequirementMatchEvidence(
        required=responsibilities,
        matched=matched,
        missing=missing,
        evidence=explanation,
    )


def _match_certifications(
    candidate_certifications: list[str],
    required_certifications: list[str],
) -> RequirementMatchEvidence:
    """Match certification names case-insensitively without scoring them."""
    candidate_values = {_canonical_text(value) for value in candidate_certifications}
    matched = [
        required for required in required_certifications
        if _canonical_text(required) in candidate_values
    ]
    missing = [item for item in required_certifications if item not in matched]
    if not required_certifications:
        explanation = "No explicit certification requirements were extracted."
    else:
        explanation = f"Candidate certifications matched {len(matched)} of {len(required_certifications)} requirements."
    return RequirementMatchEvidence(
        required=required_certifications,
        matched=matched,
        missing=missing,
        evidence=explanation,
    )


def _canonical_text(value: str) -> str:
    return " ".join(value.lower().split())


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _phrase_tokens(value: str) -> set[str]:
    return set(_tokens(value))


def _education_evidence(
    candidate: CandidateProfile,
    required_level: str,
    education_percentage: float,
) -> str:
    """Describe the deterministic education-level comparison."""
    if not required_level.strip():
        return "No education requirement specified; full component credit awarded."
    candidate_rank = max(
        (_education_rank(entry.qualification_level or entry.degree) for entry in candidate.education),
        default=0,
    )
    required_rank = _education_rank(required_level)
    if candidate_rank >= required_rank and required_rank > 0:
        return "Candidate meets the required education level."
    if education_percentage > 0:
        return "Candidate has a lower recognized education level; partial credit awarded."
    return "No matching recognized education level was found."


def _education_rank(value: str) -> int:
    """Map an education label to an ordered level, or zero when unknown."""
    normalized = value.strip().lower()
    for label, rank in sorted(_EDUCATION_LEVELS.items(), key=lambda item: -len(item[0])):
        if label in normalized:
            return rank
    return 0


def _build_skill_gaps(
    mandatory_skills: list[str],
    preferred_skills: list[str],
    candidate_skills: set[str],
) -> list[SkillGap]:
    """Create explicit gaps for each required skill absent from the profile."""
    gaps: list[SkillGap] = []
    for skill in mandatory_skills:
        if skill not in candidate_skills:
            gaps.append(SkillGap(
                skill=skill,
                category="mandatory",
                reason="Mandatory job skill was not found in the candidate profile.",
            ))
    for skill in preferred_skills:
        if skill not in candidate_skills:
            gaps.append(SkillGap(
                skill=skill,
                category="preferred",
                reason="Preferred job skill was not found in the candidate profile.",
            ))
    return gaps
