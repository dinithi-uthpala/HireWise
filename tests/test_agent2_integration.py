"""Focused tests for Agent 2 retrieval integration."""
from __future__ import annotations

from backend.agents.agent2_job_matching import agent as agent_module
from backend.agents.agent2_job_matching.agent import match_candidate_to_job
from backend.agents.agent2_job_matching.requirements import extract_job_requirements
from backend.agents.agent2_job_matching.scoring import score_candidate
from backend.schemas import CandidateProfile, EducationEntry, RetrievalEvidence


def _candidate() -> CandidateProfile:
    return CandidateProfile(
        candidate_id="CAND-INTEGRATION-001",
        technical_skills=["Python", "SQL", "Pandas"],
        education=[EducationEntry(qualification_level="Bachelor")],
        total_experience_years=1.0,
    )


def _job_description() -> str:
    return (
        "Required skills: Python, SQL. Preferred skills: Pandas. "
        "Minimum 1 year of experience. Bachelor's degree required."
    )


def test_retrieval_evidence_is_attached_without_document_content(monkeypatch) -> None:
    evidence = [
        RetrievalEvidence(
            source="data_analyst_competency_framework.md",
            category="competency_framework",
            relevance=0.91,
        )
    ]
    monkeypatch.setattr(agent_module, "retrieve_job_evidence", lambda job: (evidence, []))

    result = match_candidate_to_job(
        _candidate(), "Junior Data Analyst", _job_description(), "ok", 0.95
    )

    assert result.match_status == "scored"
    assert result.retrieval_evidence == evidence
    assert result.retrieval_evidence[0].source == "data_analyst_competency_framework.md"
    assert not hasattr(result.retrieval_evidence[0], "content")


def test_retrieval_does_not_change_deterministic_score(monkeypatch) -> None:
    candidate = _candidate()
    job, _ = extract_job_requirements("Junior Data Analyst", _job_description())
    expected = score_candidate(candidate, job).match_score
    monkeypatch.setattr(agent_module, "retrieve_job_evidence", lambda job: ([], []))

    result = match_candidate_to_job(
        candidate, "Junior Data Analyst", _job_description(), "ok", 1.0
    )

    assert result.match_score == expected


def test_retrieval_failure_preserves_scoring_and_adds_warning(monkeypatch) -> None:
    candidate = _candidate()
    job, _ = extract_job_requirements("Junior Data Analyst", _job_description())
    expected = score_candidate(candidate, job).match_score

    def fail_retrieval(job):
        raise RuntimeError("temporary Chroma failure")

    monkeypatch.setattr(agent_module, "retrieve_job_evidence", fail_retrieval)
    result = match_candidate_to_job(
        candidate, "Junior Data Analyst", _job_description(), "ok", 1.0
    )

    assert result.match_score == expected
    assert result.retrieval_evidence == []
    assert any("retrieval was unavailable" in warning.lower() for warning in result.warnings)


def test_empty_retrieval_results_do_not_crash_matching(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_module,
        "retrieve_job_evidence",
        lambda job: ([], ["No approved knowledge-base evidence was retrieved."]),
    )

    result = match_candidate_to_job(
        _candidate(), "Junior Data Analyst", _job_description(), "ok", 1.0
    )

    assert result.match_score is not None
    assert result.retrieval_evidence == []
    assert any("no approved knowledge-base evidence" in warning.lower() for warning in result.warnings)


def test_retrieval_supported_related_skill_can_satisfy_broader_requirement(monkeypatch) -> None:
    evidence = [
        RetrievalEvidence(
            source="data_analyst_competency_framework.md",
            category="competency_framework",
            relevance=0.91,
            related_skills=["Power BI", "Tableau", "Looker Studio"],
        )
    ]
    monkeypatch.setattr(
        agent_module,
        "retrieve_job_evidence",
        lambda job: (evidence, []),
    )

    result = match_candidate_to_job(
        CandidateProfile(
            candidate_id="CAND-RELATED-001",
            technical_skills=["Power BI"],
            total_experience_years=1.0,
        ),
        "Data Analyst",
        "Required skills: Data Visualization.",
        "ok",
        1.0,
        job_id="JOB-RELATED-001",
    )

    assert result.matched_mandatory_skills == ["Data Visualization"]
    assert result.skill_gaps == []
    assert result.score_evidence.mandatory_skills.related_matches == {
        "Data Visualization": ["Power BI"]
    }
    assert result.score_breakdown.mandatory_skills == 45.0
