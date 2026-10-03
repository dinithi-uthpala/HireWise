"""Fairness test on Member 2's real sample pair (same qualifications,
different identity details). If this fails it is a REAL finding: something
identity-related reached scoring."""
from pathlib import Path

import pytest

from backend.agents.agent3_responsible_decision.fairness import compare_reviews
from backend.api.pipeline import run_agents
from backend.models import JobVacancy
from backend.schemas import ReviewThresholds

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "cvs"
CV_A = SAMPLES / "fairness_pair_a_male.docx"
CV_B = SAMPLES / "fairness_pair_b_female.docx"

JOB = JobVacancy(
    job_id="JOB-FAIRNESS", job_title="Junior Data Analyst",
    job_description=("Required skills: Python, SQL, Excel. Preferred skills: Pandas, Power BI. "
                     "Minimum 1 year of relevant experience. Bachelor's degree required."),
)

pytestmark = pytest.mark.skipif(not (CV_A.exists() and CV_B.exists()),
                                reason="sample fairness CVs not found in samples/cvs")


def test_sample_pair_gets_the_same_score_and_recommendation():
    ra = run_agents(CV_A.name, CV_A.read_bytes(), JOB, ReviewThresholds())[2]
    rb = run_agents(CV_B.name, CV_B.read_bytes(), JOB, ReviewThresholds())[2]
    result = compare_reviews("Pair A", "Pair B", ra, rb)
    print(result.explanation)
    assert result.passed, result.explanation
