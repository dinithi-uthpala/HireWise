"""Database + REST tests for Agent 3 (uses an in-memory SQLite database)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from backend.agents.agent3_responsible_decision import review_candidate
from backend.agents.agent3_responsible_decision.settings_bridge import thresholds_from_settings
from backend.agents.agent3_responsible_decision.store import save_pipeline_result
from backend.api.agent3 import router
from backend.database import get_session
from backend.models_pipeline import AuditLog
from tests.test_agent3_review import make_extraction, make_match


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setattr("backend.api.agent3.default_llm_from_settings", lambda: None)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    with Session(engine) as seed:
        yield TestClient(app), seed


def seed_candidate(session, cid="CAND-001", job="JOB-1", score=88.0, parts=(40, 22, 13, 13)):
    ext = make_extraction(cid=cid)
    match = make_match(score, parts, cid=cid)
    review = review_candidate(ext, match)
    save_pipeline_result(session, job, ext, match, review)
    return ext, match, review


def test_thresholds_load_from_settings():
    th = thresholds_from_settings()
    assert 0 <= th.strong_match_min <= 100
    assert th.potential_match_min < th.strong_match_min


def test_status_endpoint_says_no_final_decision(env):
    client, _ = env
    body = client.get("/api/agent3/status").json()
    assert body["makes_final_decision"] is False


def test_review_endpoint(env):
    client, _ = env
    ext, match, _ = seed_candidate(env[1])
    r = client.post("/api/agent3/review", json={
        "extraction": ext.model_dump(mode="json"), "match": match.model_dump(mode="json")})
    assert r.status_code == 200
    body = r.json()
    assert body["human_review_required"] is True
    assert body["recommendation_code"] == "STRONG_MATCH"


def test_saved_candidates_are_listed_best_first(env):
    client, session = env
    seed_candidate(session, "CAND-001", score=70, parts=(30, 20, 10, 10))
    seed_candidate(session, "CAND-002", score=88)
    seed_candidate(session, "CAND-003", job="OTHER-JOB")
    rows = client.get("/api/jobs/JOB-1/candidates").json()
    assert [r["candidate_id"] for r in rows] == ["CAND-002", "CAND-001"]
    assert rows[0]["status"] == "awaiting_human_review"


def test_candidate_detail(env):
    client, session = env
    seed_candidate(session)
    body = client.get("/api/candidates/CAND-001").json()
    assert body["summary"]["recommendation_code"] == "STRONG_MATCH"
    assert body["review"]["human_review_required"] is True
    assert client.get("/api/candidates/NOPE").status_code == 404


def test_human_decision_flow(env):
    client, session = env
    seed_candidate(session)
    r = client.post("/api/candidates/CAND-001/decision", json={"decision": "shortlist"})
    assert r.status_code == 200
    assert r.json()["is_override"] is False
    row = client.get("/api/jobs/JOB-1/candidates").json()[0]
    assert row["status"] == "decided" and row["final_decision"] == "shortlist"


def test_override_requires_a_note(env):
    client, session = env
    seed_candidate(session)  # AI says STRONG_MATCH
    r = client.post("/api/candidates/CAND-001/decision", json={"decision": "not_selected"})
    assert r.status_code == 422
    r = client.post("/api/candidates/CAND-001/decision",
                    json={"decision": "not_selected", "note": "Role needs onsite work."})
    assert r.status_code == 200 and r.json()["is_override"] is True


def test_invalid_decision_value_is_rejected(env):
    client, session = env
    seed_candidate(session)
    assert client.post("/api/candidates/CAND-001/decision", json={"decision": "hired"}).status_code == 422
    assert client.post("/api/candidates/NOPE/decision", json={"decision": "hold"}).status_code == 404


def test_audit_trail_is_complete_and_free_of_notes(env):
    client, session = env
    seed_candidate(session)
    client.post("/api/candidates/CAND-001/decision",
                json={"decision": "not_selected", "note": "private-remark-xyz"})
    events = client.get("/api/audit/CAND-001").json()
    assert [e["action"] for e in events] == ["extracted", "scored", "reviewed", "human_decision"]
    assert "private-remark-xyz" not in json.dumps(events)
    verify = client.get("/api/audit-chain/verify").json()
    assert verify["valid"] is True and verify["entries_checked"] == 4


def test_tampering_with_the_audit_log_is_detected(env):
    client, session = env
    seed_candidate(session)
    row = session.exec(select(AuditLog)).first()
    row.summary_json = '{"match_score": 100}'
    session.add(row)
    session.commit()
    verify = client.get("/api/audit-chain/verify").json()
    assert verify["valid"] is False
    assert verify["first_bad_entry_id"] == row.id


def test_fairness_endpoint(env):
    client, session = env
    _, _, a = seed_candidate(session, "CAND-A")
    _, _, b = seed_candidate(session, "CAND-B")
    body = client.post("/api/agent3/fairness-compare", json={
        "cv_a_label": "Pair A", "cv_b_label": "Pair B",
        "review_a": a.model_dump(mode="json"), "review_b": b.model_dump(mode="json")}).json()
    assert body["passed"] is True


def test_tied_candidates_get_a_note_in_the_job_list(env):
    client, session = env
    seed_candidate(session, "CAND-001", score=88)
    seed_candidate(session, "CAND-002", score=88)
    seed_candidate(session, "CAND-003", score=70, parts=(30, 20, 10, 10))
    rows = {r["candidate_id"]: r for r in client.get("/api/jobs/JOB-1/candidates").json()}
    assert rows["CAND-001"]["batch_notes"][0].startswith("TIED_SCORE")
    assert rows["CAND-002"]["batch_notes"][0].startswith("TIED_SCORE")
    assert rows["CAND-003"]["batch_notes"] == []


def test_audit_says_the_explanation_was_rule_based(env):
    client, session = env
    seed_candidate(session)
    events = client.get("/api/audit/CAND-001").json()
    reviewed = [e for e in events if e["action"] == "reviewed"][0]
    assert reviewed["summary"]["explanation_method"] == "rule_template"
