"""Focused tests for Agent 2 requirement extraction, scoring, and orchestration."""
from __future__ import annotations

import pytest

from backend.agents.agent2_job_matching.agent import match_candidate_to_job
from backend.agents.agent2_job_matching.requirements import extract_job_requirements
from backend.agents.agent2_job_matching.scoring import score_candidate
from backend.api.agent2 import MatchRequest
from backend.config import get_settings
from backend.schemas import CandidateProfile, EducationEntry, JobRequirement


def candidate_profile() -> CandidateProfile:
    """Return a minimal profile using only the shared Agent 1 schema fields."""
    return CandidateProfile(
        candidate_id="CAND-TEST-001",
        technical_skills=["Python", "MS Excel"],
        soft_skills=[],
        education=[EducationEntry(qualification_level="Bachelor", subject="Computing")],
        total_experience_years=2.0,
    )


def complete_job_description() -> str:
    """Keep requirement sections apart for deterministic nearby-context parsing."""
    return (
        "Required: Python. "
        + ("General role information. " * 12)
        + "Preferred: Power BI. At least 2 years of experience. "
        "Bachelor degree required."
    )


def test_successful_matching_with_ok_status() -> None:
    result = match_candidate_to_job(
        candidate_profile(),
        "Data Analyst",
        complete_job_description(),
        parse_status="ok",
        extraction_confidence=0.92,
        job_id="JOB-001",
    )

    assert result.candidate_id == "CAND-TEST-001"
    assert result.job_id == "JOB-001"
    assert result.parse_status == "ok"
    assert result.match_status == "scored"
    assert result.extraction_confidence == 0.92
    assert result.match_score is not None
    assert 0 <= result.match_score <= 100


def test_swagger_example_matches_the_agent2_request_contract() -> None:
    request = MatchRequest(
        candidate={
            "candidate_id": "CAND-001",
            "technical_skills": ["Python", "SQL", "Pandas", "Power BI"],
            "soft_skills": ["Communication", "Teamwork"],
            "job_titles": ["Junior Data Analyst"],
            "education": [
                {
                    "degree": "Bachelor of Science",
                    "qualification_level": "Bachelor",
                    "subject": "Data Analytics",
                    "institution": "",
                }
            ],
            "total_experience_years": 1.0,
        },
        job_title="Junior Data Analyst",
        job_description=(
            "Required skills: Python, SQL, Excel. Preferred skills: Pandas, Power BI. "
            "Minimum 1 year of relevant experience. Bachelor's degree required."
        ),
        parse_status="ok",
        extraction_confidence=0.95,
        job_id="JOB-001",
    )

    assert request.extraction_confidence == 0.95
    assert request.candidate.candidate_id == "CAND-001"


def test_low_confidence_matching_warns_and_preserves_confidence() -> None:
    result = match_candidate_to_job(
        candidate_profile(),
        "Data Analyst",
        complete_job_description(),
        parse_status="low_confidence",
        extraction_confidence=0.41,
    )

    assert result.match_status == "warning"
    assert result.parse_status == "low_confidence"
    assert result.match_score is not None
    assert result.extraction_confidence == 0.41
    assert result.warnings
    assert any("low confidence" in warning.lower() for warning in result.warnings)


def test_failed_extraction_is_unavailable_without_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_scoring(*args: object, **kwargs: object) -> None:
        raise AssertionError("score_candidate must not run for failed extraction")

    monkeypatch.setattr(
        "backend.agents.agent2_job_matching.agent.score_candidate",
        unexpected_scoring,
    )

    result = match_candidate_to_job(
        candidate_profile(),
        "Data Analyst",
        complete_job_description(),
        parse_status="failed",
        extraction_confidence=0.0,
    )

    assert result.match_status == "unavailable"
    assert result.match_score is None
    assert result.parse_status == "failed"
    assert result.extraction_confidence == 0.0
    assert any("extraction failed" in warning.lower() for warning in result.warnings)


def test_requirement_extraction_separates_mandatory_and_preferred_skills() -> None:
    requirements, warnings = extract_job_requirements(
        "Data Analyst",
        complete_job_description(),
        job_id="JOB-REQ-001",
    )

    assert requirements.job_id == "JOB-REQ-001"
    assert requirements.title == "Data Analyst"
    assert "Python" in requirements.mandatory_skills
    assert "Power BI" in requirements.preferred_skills
    assert requirements.minimum_experience_years == 2.0
    assert requirements.required_education_level == "bachelor"
    assert not warnings


def test_preferred_skill_is_not_overridden_by_later_required_education_clause() -> None:
    requirements, _ = extract_job_requirements(
        "Data Analyst",
        "Required: Python. Preferred: Power BI. Bachelor degree required.",
    )

    assert "Python" in requirements.mandatory_skills
    assert "Power BI" in requirements.preferred_skills
    assert "Power BI" not in requirements.mandatory_skills


def test_empty_job_requirements_do_not_produce_a_perfect_match() -> None:
    result = match_candidate_to_job(
        candidate_profile(),
        "",
        "",
        parse_status="ok",
        extraction_confidence=1.0,
    )

    assert result.match_status == "unavailable"
    assert result.match_score is None
    assert any("no measurable job requirements" in warning.lower() for warning in result.warnings)


def test_scoring_reports_matches_gaps_and_uses_configured_weights() -> None:
    candidate = candidate_profile()
    job = JobRequirement(
        job_id="JOB-SCORE-001",
        title="Data Analyst",
        mandatory_skills=["Python", "SQL"],
        preferred_skills=["PowerBI"],
        minimum_experience_years=4.0,
        required_education_level="bachelor",
    )

    result = score_candidate(candidate, job)
    settings = get_settings()
    expected = (
        50.0 * settings.weight_mandatory_skills
        + 50.0 * settings.weight_experience
        + 100.0 * settings.weight_education
        + 0.0 * settings.weight_preferred_skills
    )

    assert result.matched_mandatory_skills == ["Python"]
    assert result.matched_preferred_skills == []
    assert {(gap.skill, gap.category) for gap in result.skill_gaps} == {
        ("SQL", "mandatory"),
        ("Power BI", "preferred"),
    }
    assert result.score_breakdown.mandatory_skills == round(50.0 * settings.weight_mandatory_skills, 2)
    assert result.score_breakdown.preferred_skills == 0.0
    assert result.score_breakdown.experience == round(50.0 * settings.weight_experience, 2)
    assert result.score_breakdown.education == round(100.0 * settings.weight_education, 2)
    assert result.match_score == round(expected, 2)
    assert 0 <= result.match_score <= 100
    assert any("missing mandatory skills" in warning.lower() for warning in result.warnings)


def test_score_evidence_explains_each_component_without_changing_score() -> None:
    candidate = candidate_profile()
    job = JobRequirement(
        job_id="JOB-EVIDENCE-001",
        title="Data Analyst",
        mandatory_skills=["Python", "SQL", "Power BI"],
        preferred_skills=["Excel", "Pandas"],
        minimum_experience_years=4.0,
        required_education_level="bachelor",
    )

    result = score_candidate(candidate, job)
    settings = get_settings()
    expected_score = round(
        round(33.33 * settings.weight_mandatory_skills, 2)
        + round(50.0 * settings.weight_experience, 2)
        + round(100.0 * settings.weight_education, 2)
        + round(50.0 * settings.weight_preferred_skills, 2),
        2,
    )

    assert result.match_score == expected_score
    assert result.score_evidence.mandatory_skills.score == result.score_breakdown.mandatory_skills
    assert result.score_evidence.mandatory_skills.matched == ["Python"]
    assert result.score_evidence.mandatory_skills.missing == ["SQL", "Power BI"]
    assert result.score_evidence.mandatory_skills.evidence == "Candidate matched 1 of 3 mandatory skills."

    assert result.score_evidence.preferred_skills.score == result.score_breakdown.preferred_skills
    assert result.score_evidence.preferred_skills.matched == ["Excel"]
    assert result.score_evidence.preferred_skills.missing == ["Pandas"]
    assert result.score_evidence.preferred_skills.evidence == "Candidate matched 1 of 2 preferred skills."

    assert result.score_evidence.experience.candidate_years == 2.0
    assert result.score_evidence.experience.required_years == 4.0
    assert result.score_evidence.experience.score == result.score_breakdown.experience
    assert "less than the minimum" in result.score_evidence.experience.evidence

    assert result.score_evidence.education.candidate_education == ["Bachelor"]
    assert result.score_evidence.education.required_education == "bachelor"
    assert result.score_evidence.education.score == result.score_breakdown.education
    assert result.score_evidence.education.education_match_status == "matched"
    assert result.score_evidence.education.education_contribution == 15.0
    assert result.score_evidence.education.certification_match_status == "not_required"
    assert result.score_evidence.education.total_combined_contribution == 15.0
    assert "total contribution 15.00 of 15.00" in result.score_evidence.education.evidence


def test_responsibilities_and_certifications_are_extracted_and_certifications_are_scored() -> None:
    candidate = CandidateProfile(
        candidate_id="CAND-REQUIREMENTS-001",
        technical_skills=["Python"],
        certifications=["AWS Certified Cloud Practitioner"],
        experience_entries=[],
        projects=["Build dashboards and clean data for reporting"],
    )
    job_description = (
        "Required skills: Python.\n"
        "Responsibilities: Build dashboards; Clean data for reporting\n"
        "Required certifications: AWS Certified Cloud Practitioner"
    )

    requirements, _ = extract_job_requirements("Data Analyst", job_description)
    result = score_candidate(candidate, requirements)

    assert requirements.responsibilities == [
        "Build dashboards",
        "Clean data for reporting",
    ]
    assert requirements.required_certifications == [
        "AWS Certified Cloud Practitioner"
    ]
    assert result.responsibility_evidence.matched == [
        "Build dashboards",
        "Clean data for reporting",
    ]
    assert result.certification_evidence.matched == [
        "AWS Certified Cloud Practitioner"
    ]
    assert result.score_evidence.education.certification_contribution == 15.0
    assert result.match_score is not None


def test_plain_certification_names_under_explicit_heading_are_extracted() -> None:
    requirements, _ = extract_job_requirements(
        "Cloud Administrator",
        "Required certifications:\nAWS Solutions Architect\nMicrosoft Azure Administrator",
    )

    assert requirements.required_certifications == [
        "AWS Solutions Architect",
        "Microsoft Azure Administrator",
    ]


def test_inline_certification_requirement_remains_supported() -> None:
    requirements, _ = extract_job_requirements(
        "Cloud Administrator",
        "Required certifications: AWS Certified Cloud Practitioner",
    )

    assert requirements.required_certifications == [
        "AWS Certified Cloud Practitioner"
    ]


def test_multiple_inline_certification_names_are_extracted() -> None:
    requirements, _ = extract_job_requirements(
        "Cloud Administrator",
        "Required certifications: AWS Solutions Architect; Microsoft Azure Administrator",
    )

    assert requirements.required_certifications == [
        "AWS Solutions Architect",
        "Microsoft Azure Administrator",
    ]


def test_comma_separated_inline_certifications_are_extracted() -> None:
    requirements, _ = extract_job_requirements(
        "Cloud Administrator",
        "Required certifications: AWS Solutions Architect, Microsoft Azure Administrator",
    )

    assert requirements.required_certifications == [
        "AWS Solutions Architect",
        "Microsoft Azure Administrator",
    ]


def test_certification_extraction_stops_at_next_requirement_section() -> None:
    requirements, _ = extract_job_requirements(
        "Cloud Administrator",
        "Required certifications:\nAWS Solutions Architect\n"
        "Responsibilities:\nManage cloud infrastructure\n"
        "Preferred skills: Python",
    )

    assert requirements.required_certifications == ["AWS Solutions Architect"]


def test_certification_extraction_stops_at_unrelated_prose() -> None:
    requirements, _ = extract_job_requirements(
        "Cloud Administrator",
        "Required certifications:\nAWS Solutions Architect\n"
        "Candidates should provide evidence of cloud experience.",
    )

    assert requirements.required_certifications == ["AWS Solutions Architect"]


def test_responsibility_evidence_does_not_change_score() -> None:
    candidate = candidate_profile()
    base_job = JobRequirement(
        mandatory_skills=["Python"],
        minimum_experience_years=2.0,
        required_education_level="bachelor",
    )
    enriched_job = base_job.model_copy(update={
        "responsibilities": ["Build dashboards"],
    })

    assert score_candidate(candidate, base_job).match_score == score_candidate(
        candidate, enriched_job
    ).match_score


def test_education_only_uses_full_fifteen_percent_component() -> None:
    result = score_candidate(
        candidate_profile(),
        JobRequirement(required_education_level="bachelor"),
    )

    evidence = result.score_evidence.education
    assert result.score_breakdown.education == 15.0
    assert evidence.education_match_status == "matched"
    assert evidence.education_contribution == 15.0
    assert evidence.certification_contribution == 0.0
    assert evidence.total_combined_contribution == 15.0


def test_certification_only_uses_full_fifteen_percent_component() -> None:
    candidate = candidate_profile().model_copy(
        update={"certifications": ["AWS Certified Cloud Practitioner"]}
    )
    result = score_candidate(
        candidate,
        JobRequirement(required_certifications=["AWS Certified Cloud Practitioner"]),
    )

    evidence = result.score_evidence.education
    assert result.score_breakdown.education == 15.0
    assert evidence.education_match_status == "not_required"
    assert evidence.certification_match_status == "matched"
    assert evidence.certification_contribution == 15.0
    assert evidence.total_combined_contribution == 15.0


def test_education_and_certification_split_the_existing_component_equally() -> None:
    candidate = candidate_profile().model_copy(
        update={"certifications": ["AWS Certified Cloud Practitioner"]}
    )
    result = score_candidate(
        candidate,
        JobRequirement(
            required_education_level="bachelor",
            required_certifications=["AWS Certified Cloud Practitioner"],
        ),
    )

    evidence = result.score_evidence.education
    assert result.score_breakdown.education == 15.0
    assert evidence.education_contribution == 7.5
    assert evidence.certification_contribution == 7.5
    assert evidence.total_combined_contribution == 15.0


def test_missing_certification_is_evidenced_and_receives_no_certification_credit() -> None:
    result = score_candidate(
        candidate_profile(),
        JobRequirement(required_certifications=["AWS Certified Cloud Practitioner"]),
    )

    evidence = result.score_evidence.education
    assert evidence.certification_match_status == "missing"
    assert evidence.matched_certifications == []
    assert evidence.missing_certifications == ["AWS Certified Cloud Practitioner"]
    assert evidence.certification_contribution == 0.0
    assert evidence.total_combined_contribution == 0.0


def test_all_official_components_total_one_hundred_and_education_component_is_capped() -> None:
    candidate = candidate_profile().model_copy(
        update={"certifications": ["AWS Certified Cloud Practitioner"]}
    )
    result = score_candidate(
        candidate,
        JobRequirement(
            mandatory_skills=["Python"],
            preferred_skills=["Excel"],
            minimum_experience_years=1.0,
            required_education_level="bachelor",
            required_certifications=["AWS Certified Cloud Practitioner"],
        ),
    )
    settings = get_settings()

    assert result.score_breakdown.education <= 15.0
    assert result.score_breakdown.mandatory_skills == 45.0
    assert result.score_breakdown.experience == 25.0
    assert result.score_breakdown.education == 15.0
    assert result.score_breakdown.preferred_skills == 15.0
    assert result.match_score == 100.0
    assert (
        settings.weight_mandatory_skills
        + settings.weight_experience
        + settings.weight_education
        + settings.weight_preferred_skills
        == 1.0
    )


def test_clear_skill_match_is_not_uncertain() -> None:
    result = score_candidate(
        candidate_profile(),
        JobRequirement(mandatory_skills=["Python"]),
    )

    assert result.uncertain_matches == []


def test_clear_missing_skill_is_not_uncertain() -> None:
    result = score_candidate(
        candidate_profile(),
        JobRequirement(mandatory_skills=["SQL"]),
    )

    assert result.skill_gaps[0].skill == "SQL"
    assert result.uncertain_matches == []


def test_ambiguous_skill_evidence_is_flagged_without_assuming_a_match() -> None:
    candidate = candidate_profile().model_copy(
        update={"summary": "Worked with data tools on reporting projects."}
    )
    result = score_candidate(candidate, JobRequirement(mandatory_skills=["Power BI"]))

    assert result.matched_mandatory_skills == []
    assert any(
        item.requirement_type == "skill" and item.requirement == "Power BI"
        for item in result.uncertain_matches
    )


def test_ambiguous_experience_evidence_is_flagged() -> None:
    candidate = candidate_profile().model_copy(update={"total_experience_years": 1.0})
    result = score_candidate(
        candidate,
        JobRequirement(minimum_experience_years=2.0),
    )

    assert any(item.requirement_type == "experience" for item in result.uncertain_matches)


def test_unmapped_education_evidence_is_flagged() -> None:
    candidate = candidate_profile().model_copy(update={
        "education": [EducationEntry(degree="Relevant studies")],
    })
    result = score_candidate(
        candidate,
        JobRequirement(required_education_level="bachelor"),
    )

    assert any(item.requirement_type == "education" for item in result.uncertain_matches)


def test_ambiguous_certification_evidence_is_flagged() -> None:
    candidate = candidate_profile().model_copy(update={"certifications": ["AWS"]})
    result = score_candidate(
        candidate,
        JobRequirement(required_certifications=["AWS Certified Cloud Practitioner"]),
    )

    assert result.certification_evidence.matched == []
    assert any(item.requirement_type == "certification" for item in result.uncertain_matches)


def test_partial_responsibility_evidence_is_flagged() -> None:
    candidate = candidate_profile().model_copy(
        update={"projects": ["Created dashboards for monthly reporting."]}
    )
    result = score_candidate(
        candidate,
        JobRequirement(responsibilities=["Build dashboards"]),
    )

    assert result.responsibility_evidence.matched == []
    assert any(item.requirement_type == "responsibility" for item in result.uncertain_matches)


def test_uncertainty_does_not_change_the_deterministic_score() -> None:
    clear_candidate = candidate_profile()
    ambiguous_candidate = clear_candidate.model_copy(
        update={"summary": "Worked with data tools on reporting projects."}
    )
    job = JobRequirement(mandatory_skills=["Power BI"])

    assert score_candidate(clear_candidate, job).match_score == score_candidate(
        ambiguous_candidate, job
    ).match_score
