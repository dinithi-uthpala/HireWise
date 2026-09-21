"""Tests for Agent 3 - Responsible Decision Agent.

Run:  python -m pytest tests/test_agent3_review.py -v
"""
import pytest
from pydantic import ValidationError

from backend.agents.agent3_responsible_decision import review_candidate
from backend.schemas import (
    CandidateProfile,
    EducationEntry,
    EducationScoreEvidence,
    ExperienceEntry,
    ExtractionResult,
    MatchResult,
    PIIReport,
    RetrievalEvidence,
    ReviewOutput,
    ReviewThresholds,
    ScoreBreakdown,
    ScoreEvidence,
    SkillGap,
    SkillScoreEvidence,
    ExperienceScoreEvidence,
    UncertainMatch,
)


# ---------------------------------------------------------------- helpers
def make_extraction(cid="CAND-001", confidence=0.9, parse_status="ok", **profile_kw):
    profile = CandidateProfile(
        candidate_id=cid,
        technical_skills=["Python", "SQL", "Excel"],
        **profile_kw,
    )
    return ExtractionResult(
        candidate_id=cid,
        profile=profile,
        pii=PIIReport(detected_count=3, redacted_text="Junior analyst with Python and SQL."),
        extraction_confidence=confidence,
        parse_status=parse_status,
    )


def make_match(score=88.0, breakdown=(40, 22, 13, 13), cid="CAND-001", **overrides):
    m, e, ed, p = breakdown
    base = dict(
        candidate_id=cid,
        job_id="JOB-1",
        match_status="scored",
        match_score=score,
        score_breakdown=ScoreBreakdown(
            mandatory_skills=m, experience=e, education=ed, preferred_skills=p
        ),
        matched_mandatory_skills=["Python", "SQL", "Excel"],
        retrieval_evidence=[RetrievalEvidence(source="skill_taxonomy.md", category="taxonomy")],
        score_evidence=ScoreEvidence(
            mandatory_skills=SkillScoreEvidence(score=100, evidence="All mandatory skills found."),
            preferred_skills=SkillScoreEvidence(score=80, evidence="Power BI found."),
            experience=ExperienceScoreEvidence(score=90, evidence="1.5 years of relevant work."),
            education=EducationScoreEvidence(score=13, evidence="BSc in IT."),
        ),
    )
    base.update(overrides)
    return MatchResult(**base)


def codes(review):
    return {f.code for f in review.risk_flags}


# ---------------------------------------------------------------- recommendations
def test_strong_match_when_high_score_and_no_flags():
    r = review_candidate(make_extraction(), make_match(88, (40, 22, 13, 13)))
    assert r.recommendation_code == "STRONG_MATCH"
    assert r.risk_flags == []
    assert r.privacy_check.passed


def test_potential_match_when_mandatory_skill_missing():
    m = make_match(
        70, (30, 20, 10, 10),
        skill_gaps=[SkillGap(skill="Tableau", category="mandatory", reason="Not in CV")],
    )
    r = review_candidate(make_extraction(), m)
    assert r.recommendation_code == "POTENTIAL_MATCH"
    assert "MISSING_MANDATORY_SKILLS" in codes(r)


def test_insufficient_evidence_below_60():
    r = review_candidate(make_extraction(), make_match(40, (20, 10, 5, 5)))
    assert r.recommendation_code == "INSUFFICIENT_EVIDENCE"


def test_borderline_score_is_not_strong():
    r = review_candidate(make_extraction(), make_match(81, (37, 22, 11, 11)))
    assert "BORDERLINE_SCORE" in codes(r)
    assert r.recommendation_code == "POTENTIAL_MATCH"


def test_points_without_evidence_gives_insufficient_evidence():
    m = make_match(85, (40, 22, 12, 11))
    m.score_evidence.mandatory_skills.evidence = ""
    r = review_candidate(make_extraction(), m)
    assert "MISSING_SCORE_EVIDENCE" in codes(r)
    assert r.recommendation_code == "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------- human-review rules
def test_low_extraction_confidence_forces_manual_review():
    r = review_candidate(make_extraction(confidence=0.5), make_match())
    assert "LOW_EXTRACTION_CONFIDENCE" in codes(r)
    assert r.recommendation_code == "MANUAL_REVIEW"


def test_low_quality_parse_forces_manual_review():
    r = review_candidate(make_extraction(parse_status="low_confidence"), make_match())
    assert r.recommendation_code == "MANUAL_REVIEW"


def test_low_matching_confidence_forces_manual_review():
    unc = [UncertainMatch(requirement_type="skill", requirement=f"Skill{i}", reason="unclear")
           for i in range(5)]
    r = review_candidate(make_extraction(), make_match(uncertain_matches=unc))
    assert r.matching_confidence == 0.5
    assert "LOW_MATCHING_CONFIDENCE" in codes(r)
    assert r.recommendation_code == "MANUAL_REVIEW"


def test_unavailable_match_forces_manual_review():
    m = make_match(score=None, match_status="unavailable")
    r = review_candidate(make_extraction(), m)
    assert r.recommendation_code == "MANUAL_REVIEW"
    assert r.matching_confidence == 0.0
    assert "MATCH_UNAVAILABLE" in codes(r)


def test_inconsistent_score_forces_manual_review():
    r = review_candidate(make_extraction(), make_match(90, (10, 10, 5, 5)))
    assert "SCORE_INCONSISTENT" in codes(r)
    assert r.recommendation_code == "MANUAL_REVIEW"


def test_candidate_id_mismatch_forces_manual_review():
    r = review_candidate(make_extraction(cid="CAND-001"), make_match(cid="CAND-002"))
    assert "CANDIDATE_ID_MISMATCH" in codes(r)
    assert r.recommendation_code == "MANUAL_REVIEW"


# ---------------------------------------------------------------- privacy
def test_email_in_profile_fails_privacy_and_is_never_repeated():
    secret = "kamal.perera@example.com"
    r = review_candidate(make_extraction(summary=f"Contact {secret} for more"), make_match())
    assert not r.privacy_check.passed
    assert r.recommendation_code == "MANUAL_REVIEW"
    assert secret not in r.explanation
    assert all(secret not in v for v in r.privacy_check.violations)


def test_phone_number_detected():
    r = review_candidate(make_extraction(summary="Call +94 77 123 4567"), make_match())
    assert not r.privacy_check.passed


def test_nic_detected():
    r = review_candidate(make_extraction(summary="NIC 199012345678"), make_match())
    assert not r.privacy_check.passed


def test_year_range_is_not_mistaken_for_a_phone_number():
    exp = ExperienceEntry(role="Analyst", employer="Acme", start="2019", end="2021",
                          summary="Worked 2019 - 2021 on dashboards")
    r = review_candidate(make_extraction(experience_entries=[exp]), make_match())
    assert r.privacy_check.passed


def test_institution_name_in_scoring_evidence_is_caught():
    edu = EducationEntry(degree="BSc", subject="IT", institution="Zenith University")
    m = make_match()
    m.score_evidence.education.evidence = "BSc from Zenith University"
    r = review_candidate(make_extraction(education=[edu]), m)
    assert not r.privacy_check.passed
    assert "Zenith" not in r.explanation


def test_institution_kept_in_profile_but_unused_in_scoring_is_fine():
    edu = EducationEntry(degree="BSc", subject="IT", institution="Zenith University")
    r = review_candidate(make_extraction(education=[edu]), make_match())
    assert r.privacy_check.passed


def test_prohibited_attribute_in_evidence_is_caught():
    m = make_match()
    m.score_evidence.experience.evidence = "Strong candidate for a female applicant"
    r = review_candidate(make_extraction(), m)
    assert not r.privacy_check.passed


# ---------------------------------------------------------------- responsible-AI guarantees
def test_human_review_is_always_required():
    r = review_candidate(make_extraction(), make_match())
    assert r.human_review_required is True
    assert "human recruiter" in r.explanation


def test_ai_output_cannot_claim_human_review_is_not_needed():
    r = review_candidate(make_extraction(), make_match())
    data = r.model_dump()
    data["human_review_required"] = False
    with pytest.raises(ValidationError):
        ReviewOutput(**data)


def test_no_label_ever_says_rejected():
    for score in (0, 30, 59, 61, 79, 85, 99):
        r = review_candidate(make_extraction(), make_match(score, (score * .45, score * .25, score * .15, score * .15)))
        assert "reject" not in r.recommendation.lower()


def test_custom_thresholds_are_respected():
    th = ReviewThresholds(strong_match_min=70, potential_match_min=50)
    r = review_candidate(make_extraction(), make_match(75, (34, 19, 11, 11)), th)
    assert r.recommendation_code == "STRONG_MATCH"
