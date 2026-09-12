"""API-level tests for the Agent 2 FastAPI endpoints."""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.agents.agent2_job_matching import agent as agent2_agent
from backend.main import app
from backend.schemas import MatchResult, RetrievalEvidence


client = TestClient(app)


VALID_REQUEST = {
    "candidate": {
        "candidate_id": "CAND-API-001",
        "technical_skills": ["Python", "SQL", "Pandas"],
        "soft_skills": ["Communication", "Teamwork"],
        "job_titles": ["Junior Data Analyst"],
        "employers": [],
        "education": [
            {
                "degree": "Bachelor of Science",
                "qualification_level": "Bachelor",
                "subject": "Data Analytics",
                "institution": "",
            }
        ],
        "certifications": [],
        "projects": [],
        "experience_entries": [],
        "total_experience_years": 2.0,
        "summary": "Junior Data Analyst with Python and SQL experience.",
    },
    "job_title": "Junior Data Analyst",
    "job_description": (
        "Required skills: Python, SQL, Excel. "
        "Preferred skills: Pandas, Power BI. "
        "Minimum 1 year of relevant experience. "
        "Bachelor's degree required."
    ),
    "parse_status": "ok",
    "extraction_confidence": 0.95,
    "job_id": "JOB-API-001",
}


FAKE_RETRIEVAL_EVIDENCE = [
    RetrievalEvidence(
        source="data_analyst_competency_framework.md",
        category="competency_framework",
        relevance=0.91,
    )
]


def test_agent2_status_returns_ready_response() -> None:
    response = client.get("/api/agent2/status")

    assert response.status_code == 200
    assert response.json() == {"agent": "job_matching", "status": "ready"}


def test_agent2_match_returns_complete_valid_response(monkeypatch) -> None:
    monkeypatch.setattr(
        agent2_agent,
        "retrieve_job_evidence",
        lambda job: (FAKE_RETRIEVAL_EVIDENCE, []),
        raising=False,
    )

    response = client.post("/api/agent2/match", json=VALID_REQUEST)

    assert response.status_code == 200
    payload = response.json()
    result = MatchResult.model_validate(payload)

    assert result.match_score is not None
    assert result.score_breakdown is not None
    assert result.score_evidence is not None
    assert result.retrieval_evidence == FAKE_RETRIEVAL_EVIDENCE
    assert result.matched_mandatory_skills
    assert result.matched_preferred_skills
    assert result.skill_gaps
    assert isinstance(result.uncertain_matches, list)
    assert isinstance(result.warnings, list)


def test_agent2_match_exposes_all_score_evidence_components(monkeypatch) -> None:
    monkeypatch.setattr(
        agent2_agent,
        "retrieve_job_evidence",
        lambda job: (FAKE_RETRIEVAL_EVIDENCE, []),
        raising=False,
    )

    payload = client.post("/api/agent2/match", json=VALID_REQUEST).json()
    evidence = payload["score_evidence"]

    assert set(evidence) == {"mandatory_skills", "preferred_skills", "experience", "education"}
    assert evidence["mandatory_skills"]["matched"] == ["Python", "SQL"]
    assert evidence["mandatory_skills"]["missing"] == ["Excel"]
    assert evidence["preferred_skills"]["matched"] == ["Pandas"]
    assert evidence["preferred_skills"]["missing"] == ["Power BI"]
    assert evidence["experience"]["candidate_years"] == 2.0
    assert evidence["experience"]["required_years"] == 1.0
    assert evidence["education"]["candidate_education"] == ["Bachelor"]
    assert evidence["education"]["required_education"] == "bachelor"


def test_agent2_match_retrieval_failure_still_returns_scored_response(monkeypatch) -> None:
    def fail_retrieval(job):
        raise RuntimeError("temporary retrieval failure")

    monkeypatch.setattr(
        agent2_agent,
        "retrieve_job_evidence",
        fail_retrieval,
        raising=False,
    )

    response = client.post("/api/agent2/match", json=VALID_REQUEST)

    assert response.status_code == 200
    result = MatchResult.model_validate(response.json())
    assert result.match_score is not None
    assert result.retrieval_evidence == []
    assert any("retrieval was unavailable" in warning.lower() for warning in result.warnings)


def test_agent2_match_rejects_invalid_request_payload() -> None:
    invalid_request = {
        "candidate": {"candidate_id": "CAND-INVALID"},
        "job_title": "Junior Data Analyst",
        "job_description": "Required skills: Python.",
        "parse_status": "not-a-valid-status",
        "extraction_confidence": 1.5,
    }

    response = client.post("/api/agent2/match", json=invalid_request)

    assert response.status_code == 422
    assert "detail" in response.json()


def test_job_creation_persists_and_returns_job() -> None:
    job_id = f"JOB-CREATE-{uuid4().hex[:8].upper()}"
    response = client.post(
        "/api/agent2/jobs",
        json={
            "job_id": job_id,
            "job_title": "Data Analyst",
            "job_description": "Required skills: Python. Minimum 1 year experience.",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["job_title"] == "Data Analyst"
    assert payload["created_at"]


def test_job_creation_rejects_invalid_job_id() -> None:
    response = client.post(
        "/api/agent2/jobs",
        json={
            "job_id": "invalid job id",
            "job_title": "Data Analyst",
            "job_description": "Required skills: Python.",
        },
    )

    assert response.status_code == 422


def test_job_creation_generates_job_id_when_omitted() -> None:
    response = client.post(
        "/api/agent2/jobs",
        json={
            "job_title": "Generated ID Analyst",
            "job_description": "Required skills: Python.",
        },
    )

    assert response.status_code == 201
    job_id = response.json()["job_id"]
    assert job_id.startswith("JOB-")
    assert len(job_id) == 16


def test_job_creation_rejects_duplicate_job_id() -> None:
    job_id = f"JOB-DUPLICATE-{uuid4().hex[:8].upper()}"
    payload = {
        "job_id": job_id,
        "job_title": "Duplicate Test Analyst",
        "job_description": "Required skills: Python.",
    }

    first_response = client.post("/api/agent2/jobs", json=payload)
    second_response = client.post("/api/agent2/jobs", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_matching_rejects_unknown_persisted_job_id() -> None:
    request = {
        **VALID_REQUEST,
        "job_id": "JOB-DOES-NOT-EXIST",
        "job_title": "",
        "job_description": "",
    }

    response = client.post("/api/agent2/match", json=request)

    assert response.status_code == 404


def test_matching_uses_persisted_job() -> None:
    job_id = f"JOB-STORED-{uuid4().hex[:8].upper()}"
    create_response = client.post(
        "/api/agent2/jobs",
        json={
            "job_id": job_id,
            "job_title": "Stored Data Analyst",
            "job_description": "Required skills: Python, SQL. Bachelor degree required.",
        },
    )
    assert create_response.status_code == 201

    response = client.post(
        "/api/agent2/match",
        json={**VALID_REQUEST, "job_id": job_id, "job_title": "", "job_description": ""},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["score_evidence"]["mandatory_skills"]["matched"] == ["Python", "SQL"]


def test_existing_direct_matching_remains_compatible() -> None:
    response = client.post("/api/agent2/match", json=VALID_REQUEST)

    assert response.status_code == 200
    assert response.json()["job_id"] == "JOB-API-001"


def test_api_serializes_structured_uncertainty_fields() -> None:
    request = {
        **VALID_REQUEST,
        "candidate": {
            **VALID_REQUEST["candidate"],
            "summary": "Worked with data tools on reporting projects.",
        },
        "job_description": "Required skills: Power BI.",
    }

    response = client.post("/api/agent2/match", json=request)

    assert response.status_code == 200
    uncertain_matches = response.json()["uncertain_matches"]
    assert uncertain_matches
    assert set(uncertain_matches[0]) == {
        "requirement_type",
        "requirement",
        "reason",
        "candidate_evidence",
    }
