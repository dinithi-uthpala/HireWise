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

    if not mandatory_skills and not preferred_skills and not job.minimum_experience_years and not job.required_education_level.strip():
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
        education=round(education_percentage * settings.weight_education, 2),
    )

    candidate_education = _candidate_education_labels(candidate)
    responsibility_evidence = _match_responsibilities(candidate, job.responsibilities)
    certification_evidence = _match_certifications(
        candidate.certifications, job.required_certifications
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
            evidence=_education_evidence(
                candidate, job.required_education_level, education_percentage
            ),
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
        warnings=warnings,
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
