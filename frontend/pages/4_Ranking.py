"""Candidate ranking and comparison for the currently selected job."""
from __future__ import annotations

import os
import time

import pandas as pd
import requests
import streamlit as st

try:
    from frontend.job_selection import open_page, render_job_selector
except ModuleNotFoundError:  # Streamlit runs pages with frontend on sys.path.
    from job_selection import open_page, render_job_selector

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def response_detail(response: requests.Response) -> str:
    try:
        return str(response.json().get("detail") or f"HTTP {response.status_code}")
    except ValueError:
        return f"HTTP {response.status_code}"


def load_candidates(job_id: str) -> list[dict]:
    response = requests.get(f"{API_BASE_URL}/api/jobs/{job_id}/candidates", timeout=30)
    if not response.ok:
        raise ValueError(response_detail(response))
    return sorted(response.json(), key=lambda candidate: candidate.get("match_score") or -1, reverse=True)


def load_candidates_with_retry(job_id: str) -> list[dict]:
    """Retry once when a just-completed pipeline has not appeared yet."""

    candidates = load_candidates(job_id)
    if not candidates:
        time.sleep(0.25)
        candidates = load_candidates(job_id)
    return candidates


st.title("Candidate Results")
st.caption("Review transparent AI matching results before making a human decision.")
st.warning("Recruiter review required")

job_id = render_job_selector()
if not job_id:
    st.stop()

if job_id != st.session_state.get("results_job_id") or not st.session_state.get("candidate_results"):
    try:
        with st.spinner("Loading candidates..."):
            st.session_state["candidate_results"] = load_candidates_with_retry(job_id)
        st.session_state["results_job_id"] = job_id
        st.session_state.pop("selected_candidate_id", None)
    except (requests.RequestException, ValueError) as exc:
        st.session_state["candidate_results"] = []
        st.error(f"Could not load candidates: {exc}")

if st.button("Refresh candidates"):
    try:
        with st.spinner("Loading candidates..."):
            st.session_state["candidate_results"] = load_candidates_with_retry(job_id)
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Could not load candidates: {exc}")

candidates = st.session_state.get("candidate_results", [])
if not candidates:
    st.info("No candidates were found for this job.")
    st.stop()
    # ``st.stop`` only halts an active Streamlit script. Keep ordinary imports
    # (including tooling that imports page modules) safe as well.
    candidates = [{"candidate_id": "", "match_score": None}]

st.subheader("Ranked candidates")
st.dataframe(
    pd.DataFrame(
        {
            "Candidate": candidate["candidate_id"],
            "Score": candidate.get("match_score"),
            "Recommendation": candidate.get("recommendation", ""),
            "Risk flags": ", ".join(candidate.get("risk_flag_codes", [])) or "None",
            "Status": candidate.get("status", ""),
        }
        for candidate in candidates
    ),
    use_container_width=True,
    hide_index=True,
)

candidate_ids = [candidate["candidate_id"] for candidate in candidates]
current_candidate = st.session_state.get("selected_candidate_id", candidate_ids[0])
selected_candidate_id = st.selectbox(
    "Candidate to review",
    candidate_ids,
    index=candidate_ids.index(current_candidate) if current_candidate in candidate_ids else 0,
)
st.session_state["selected_candidate_id"] = selected_candidate_id

if st.button("Open candidate detail", type="primary"):
    st.session_state["job_id"] = job_id
    st.session_state["selected_candidate_id"] = selected_candidate_id
    open_page("pages/5_Candidate_Detail.py")

selected_summary = next(
    candidate for candidate in candidates if candidate["candidate_id"] == selected_candidate_id
)
st.markdown("#### Selected candidate summary")
left, right = st.columns(2)
left.metric(
    "Overall score",
    "Not available" if selected_summary.get("match_score") is None else f"{selected_summary['match_score']:.1f}",
)
right.write("**Recommendation**")
right.write(selected_summary.get("recommendation", "No recommendation provided."))

try:
    with st.spinner("Loading candidate comparison details..."):
        detail_response = requests.get(
            f"{API_BASE_URL}/api/candidates/{selected_candidate_id}", timeout=30
        )
    if not detail_response.ok:
        st.error(response_detail(detail_response))
        detail = {}
    else:
        detail = detail_response.json()
except requests.RequestException as exc:
    st.error(f"Could not load candidate details: {exc}")
    detail = {}

match = detail.get("match", {})
review = detail.get("review", {})
if match:
    st.markdown("#### Score breakdown")
    st.dataframe(
        pd.DataFrame(
            {
                "Component": name.replace("_", " ").title(),
                "Score": score,
            }
            for name, score in match.get("score_breakdown", {}).items()
        ),
        use_container_width=True,
        hide_index=True,
    )
    skill_left, skill_right = st.columns(2)
    skill_left.write("**Matched skills**")
    skill_left.write(
        ", ".join(
            match.get("matched_mandatory_skills", [])
            + match.get("matched_preferred_skills", [])
        )
        or "None recorded"
    )
    skill_right.write("**Missing skills**")
    skill_right.write(
        ", ".join(gap.get("skill", "") for gap in match.get("skill_gaps", []))
        or "None recorded"
    )
    st.write("**Risk flags**")
    for flag in review.get("risk_flags", []):
        st.warning(f"{flag.get('code', 'Risk flag')}: {flag.get('message', '')}")
    if not review.get("risk_flags", []):
        st.write("None recorded")

for note in selected_summary.get("batch_notes", []):
    st.warning(note) if note.startswith("UNUSUAL_SCORE_PATTERN") else st.info(note)
