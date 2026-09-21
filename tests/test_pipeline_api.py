"""End-to-end tests: CV upload -> Agent 1 -> Agent 2 -> Agent 3 -> database.

These use the REAL agents, so they also act as integration tests for the team.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.api.agent3 import router as agent3_router
from backend.api.pipeline import router as pipeline_router
from backend.database import get_session
from backend.models import JobVacancy

VALID_CODES = {"STRONG_MATCH", "POTENTIAL_MATCH", "INSUFFICIENT_EVIDENCE", "MANUAL_REVIEW"}

JOB_TEXT = ("Required skills: Python, SQL, Excel. Preferred skills: Pandas, Power BI. "
            "Minimum 1 year of relevant experience. Bachelor's degree required.")


def make_cv(name, email, phone):
    return f"""{name}
{email}
{phone}
Colombo, Sri Lanka

Professional Summary
Junior Data Analyst with 2 years of experience in data cleaning, reporting and dashboards.

Skills
Python, SQL, Excel, Pandas, Power BI, Communication, Teamwork

Experience
Data Analyst Intern, Acme Analytics (Jan 2023 - Dec 2024)
- Cleaned and analysed sales data using Python and SQL.
- Built weekly Power BI dashboards for the management team.

Education
BSc (Hons) in Information Technology, 2022

Certifications
Google Data Analytics Certificate
""".encode("utf-8")


CV_A = make_cv("Kamal Perera", "kamal.perera@example.com", "+94 77 123 4567")
CV_B = make_cv("Nimali Fernando", "nimali.fernando@example.org", "+94 71 987 6543")


@pytest.fixture()
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    app = FastAPI()
    app.include_router(pipeline_router, prefix="/api")
    app.include_router(agent3_router, prefix="/api")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    with Session(engine) as seed:
        seed.add(JobVacancy(job_id="JOB-1", job_title="Junior Data Analyst", job_description=JOB_TEXT))
        seed.commit()
    yield TestClient(app)


def upload(client, content=CV_A, filename="cv.txt", job_id="JOB-1"):
    return client.post("/api/pipeline/run", data={"job_id": job_id},
                       files=[("files", (filename, content, "text/plain"))])


def test_full_pipeline_gives_a_cautious_recommendation(env):
    r = upload(env)
    assert r.status_code == 200, r.text
    item = r.json()[0]
    assert item["status"] == "processed", item
    assert item["candidate"]["recommendation_code"] in VALID_CODES
    assert item["candidate"]["status"] == "awaiting_human_review"


def test_result_appears_in_the_job_candidate_list(env):
    cid = upload(env).json()[0]["candidate"]["candidate_id"]
    rows = env.get("/api/jobs/JOB-1/candidates").json()
    assert [r["candidate_id"] for r in rows] == [cid]


def test_email_and_phone_are_never_stored(env):
    cid = upload(env).json()[0]["candidate"]["candidate_id"]
    stored = json.dumps(env.get(f"/api/candidates/{cid}").json())
    assert "kamal.perera@example.com" not in stored
    assert "77 123 4567" not in stored


def test_candidate_name_is_not_stored(env):
    """If ONLY this test fails, it is a real PII gap in Agent 1's name detection."""
    cid = upload(env).json()[0]["candidate"]["candidate_id"]
    stored = json.dumps(env.get(f"/api/candidates/{cid}").json())
    assert "Kamal" not in stored and "Perera" not in stored


def test_audit_trail_records_all_three_agents(env):
    cid = upload(env).json()[0]["candidate"]["candidate_id"]
    actions = [e["action"] for e in env.get(f"/api/audit/{cid}").json()]
    assert actions == ["extracted", "scored", "reviewed"]
    assert env.get("/api/audit-chain/verify").json()["valid"] is True


def test_human_can_decide_after_the_pipeline(env):
    cid = upload(env).json()[0]["candidate"]["candidate_id"]
    r = env.post(f"/api/candidates/{cid}/decision", json={"decision": "hold"})
    assert r.status_code == 200
    assert env.get(f"/api/candidates/{cid}").json()["summary"]["status"] == "decided"


def test_unknown_job_returns_404(env):
    assert upload(env, job_id="NOPE").status_code == 404


def test_bad_file_type_is_reported_without_crashing(env):
    r = upload(env, content=b"MZ not a cv", filename="virus.exe")
    assert r.status_code == 200
    item = r.json()[0]
    assert item["status"] == "error" and item["candidate"] is None


def test_one_bad_file_does_not_stop_the_batch(env):
    r = env.post("/api/pipeline/run", data={"job_id": "JOB-1"}, files=[
        ("files", ("virus.exe", b"MZ", "application/octet-stream")),
        ("files", ("cv.txt", CV_A, "text/plain")),
    ])
    assert [i["status"] for i in r.json()] == ["error", "processed"]


def test_fairness_pair_with_different_identities_passes(env):
    r = env.post("/api/pipeline/fairness-test", data={"job_id": "JOB-1"}, files={
        "file_a": ("a.txt", CV_A, "text/plain"),
        "file_b": ("b.txt", CV_B, "text/plain"),
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is True, body["explanation"]
    assert body["difference"] == 0
