"""Paired-CV fairness test."""
from __future__ import annotations

import os

import requests
import streamlit as st

try:
    from frontend.job_selection import render_job_selector
except ModuleNotFoundError:  # Streamlit runs pages with frontend on sys.path.
    from job_selection import render_job_selector

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def response_detail(response: requests.Response) -> str:
    """Return useful backend error text when it provides one."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    return str(body.get("detail") or f"HTTP {response.status_code}")


st.title("Fairness Test")
st.caption(
    "Identity details are removed before scoring, so candidates with equal "
    "qualifications should score equally. For a quick demo, use "
    "samples/cvs/fairness_pair_a_male.docx and "
    "samples/cvs/fairness_pair_b_female.docx."
)

job_id = render_job_selector()
if not job_id:
    st.stop()

with st.form("fairness_test_form"):
    file_a = st.file_uploader(
        "CV A",
        type=["pdf", "docx", "txt"],
        help="Upload the first CV in the qualification-matched pair.",
    )
    file_b = st.file_uploader(
        "CV B",
        type=["pdf", "docx", "txt"],
        help="Upload the second CV with different identity details.",
    )
    tolerance = st.slider(
        "Allowed score difference",
        min_value=0.0,
        max_value=5.0,
        value=0.5,
        step=0.1,
    )
    run_test = st.form_submit_button("Run fairness test", type="primary")

if run_test:
    if not job_id:
        st.error("Select a saved job before running the fairness test.")
    elif not file_a or not file_b:
        st.error("Upload both CV A and CV B before running the fairness test.")
    else:
        form_data = {"job_id": job_id, "tolerance": str(tolerance)}
        files = {
            "file_a": (file_a.name, file_a.getvalue(), file_a.type or "application/octet-stream"),
            "file_b": (file_b.name, file_b.getvalue(), file_b.type or "application/octet-stream"),
        }
        with st.spinner("Running both CVs through the fairness test..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/pipeline/fairness-test",
                    data=form_data,
                    files=files,
                    timeout=120,
                )
                if response.status_code in (400, 404):
                    st.error(response_detail(response))
                elif not response.ok:
                    st.error(response_detail(response))
                else:
                    response.raise_for_status()
                    st.session_state["fairness_job_id"] = job_id
                    st.session_state["fairness_result"] = response.json()
            except requests.exceptions.ConnectionError:
                st.error(
                    "Backend is not running. Start it with: "
                    "uvicorn backend.main:app --reload --port 8000"
                )
            except requests.RequestException as exc:
                st.error(f"Backend request failed: {exc}")

result = st.session_state.get("fairness_result")
if result:
    st.divider()
    if result.get("passed"):
        st.success("## PASS", icon="✅")
    else:
        st.error("## FAIL", icon="❌")

    score_a, score_b, difference = st.columns(3)
    score_a.metric("CV A score", "Not available" if result.get("score_a") is None else f"{result['score_a']:.2f}")
    score_b.metric("CV B score", "Not available" if result.get("score_b") is None else f"{result['score_b']:.2f}")
    difference.metric(
        "Difference",
        "Not available" if result.get("difference") is None else f"{result['difference']:.2f}",
    )
    st.write("**Explanation**")
    st.write(result.get("explanation", "No explanation provided."))
