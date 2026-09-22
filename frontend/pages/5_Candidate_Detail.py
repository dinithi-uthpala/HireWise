"""Candidate detail and score explanation."""
from __future__ import annotations

import os

import requests
import streamlit as st

try:
    from frontend.auth import auth_headers, require_login
except ModuleNotFoundError:
    from auth import auth_headers, require_login

try:
    from frontend.job_selection import select_saved_job
except ModuleNotFoundError:
    from job_selection import select_saved_job

require_login()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def response_detail(response: requests.Response) -> str:
    """Return useful backend error text when it provides one."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    return str(body.get("detail") or f"HTTP {response.status_code}")


def show_backend_error(exc: requests.RequestException) -> None:
    if isinstance(exc, requests.exceptions.ConnectionError):
        st.error(
            "Backend is not running. Start it with: "
            "uvicorn backend.main:app --reload --port 8000"
        )
        return
    st.error(
        "Could not reach the FastAPI backend. Check that it is running and "
        f"available at {API_BASE_URL}."
    )


st.title("Candidate Detail")
st.caption("Review the evidence behind a candidate's matching score.")

selected_job = select_saved_job(
    API_BASE_URL,
    auth_headers(),
    "detail_job_title",
)
load_candidates = st.button(
    "Load candidates",
    type="primary",
    disabled=selected_job is None,
)

if load_candidates:
    job_id = selected_job["job_id"]
    try:
        with st.spinner("Loading candidates..."):
            response = requests.get(
                f"{API_BASE_URL}/api/jobs/{job_id}/candidates",
                headers=auth_headers(),
                timeout=30,
            )
        if not response.ok:
            st.error(response_detail(response))
        else:
            response.raise_for_status()
            st.session_state["detail_job_id"] = job_id
            st.session_state["detail_candidates"] = response.json()
            st.session_state.pop("detail_candidate_id", None)
            st.session_state.pop("detail_loaded_candidate_id", None)
            st.session_state.pop("detail_data", None)
    except requests.RequestException as exc:
        show_backend_error(exc)

candidates = st.session_state.get("detail_candidates", [])
if st.session_state.get("detail_job_id") and not candidates:
    st.info("No candidates were found for this job.")
    st.stop()

if not candidates:
    st.info("Select a saved job role and load candidates to view candidate details.")
    st.stop()

candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
candidate_ids = list(candidate_by_id)
selected_candidate_id = st.selectbox(
    "Candidate",
    candidate_ids,
    index=(
        candidate_ids.index(st.session_state.get("detail_candidate_id"))
        if st.session_state.get("detail_candidate_id") in candidate_ids
        else 0
    ),
    format_func=lambda candidate_id: (
        f"{candidate_id} | score: "
        f"{candidate_by_id[candidate_id].get('match_score', 'N/A')} | "
        f"{candidate_by_id[candidate_id].get('recommendation', 'No recommendation')}"
    ),
    key="detail_candidate_id",
)

if selected_candidate_id != st.session_state.get("detail_loaded_candidate_id"):
    try:
        with st.spinner("Loading candidate details..."):
            response = requests.get(
                f"{API_BASE_URL}/api/candidates/{selected_candidate_id}",
                headers=auth_headers(),
                timeout=30,
            )
        if not response.ok:
            st.error(response_detail(response))
            st.stop()
        response.raise_for_status()
        st.session_state["detail_data"] = response.json()
        st.session_state["detail_loaded_candidate_id"] = selected_candidate_id
    except requests.RequestException as exc:
        show_backend_error(exc)
        st.stop()

detail = st.session_state.get("detail_data", {})
match = detail.get("match", {})
review = detail.get("review", {})
summary = detail.get("summary", {})

st.subheader(f"Candidate: {selected_candidate_id}")
score = match.get("match_score")
match_available = match.get("match_status") != "unavailable" and score is not None
left, right = st.columns(2)
left.metric("Overall score", f"{score:.1f}" if match_available else "Not available")
right.write("**Recommendation**")
right.write(summary.get("recommendation", "No recommendation provided."))

confidence_left, confidence_right = st.columns(2)
confidence_left.metric("Extraction confidence", f"{summary.get('extraction_confidence', 0):.0%}")
confidence_right.metric("Matching confidence", f"{review.get('matching_confidence', 0):.0%}")
if not match_available:
    st.error("No reliable match score was produced. Check the job requirements and CV extraction.")
elif summary.get("extraction_confidence", 0) < 0.75:
    st.warning("Low extraction confidence. Review the original CV before relying on this result.")
st.info("Recruiter review required. The AI does not make the final hiring decision.")

st.markdown("#### Why this score?")
st.caption("The score is shown with its component evidence and review signals.")

st.write("**Score breakdown**")
breakdown = match.get("score_breakdown", {})
component_labels = {
    "mandatory_skills": "Mandatory skills",
    "experience": "Experience",
    "education": "Education",
    "preferred_skills": "Preferred skills",
}
for component in component_labels:
    component_score = breakdown.get(component, 0)
    st.write(f"**{component_labels[component]}: {component_score:.1f}**")
    st.progress(max(0.0, min(float(component_score) / 100, 1.0)))

st.write("**Matched skills**")
matched_mandatory = match.get("matched_mandatory_skills", [])
matched_preferred = match.get("matched_preferred_skills", [])
if matched_mandatory or matched_preferred:
    for skill in matched_mandatory:
        st.success(f"Mandatory: {skill}")
    for skill in matched_preferred:
        st.success(f"Preferred: {skill}")
else:
    st.write("No matched skills recorded.")

st.write("**Skill gaps**")
skill_gaps = match.get("skill_gaps", [])
if skill_gaps:
    for gap in skill_gaps:
        st.warning(
            f"{gap.get('skill', 'Unknown skill')} "
            f"({gap.get('category', 'unknown')}): {gap.get('reason', 'No reason provided.')}"
        )
else:
    st.write("No skill gaps recorded.")

st.write("**Uncertain matches**")
uncertain_matches = match.get("uncertain_matches", [])
if uncertain_matches:
    for item in uncertain_matches:
        st.info(
            f"Not confirmed: {item.get('requirement', 'Unknown requirement')} - "
            f"{item.get('reason', 'No reason provided.')}"
        )
else:
    st.write("No uncertain matches recorded.")

st.write("**Explanation**")
method = review.get("explanation_method", "rule_template")
st.caption("Explanation source: " + ("Gemini LLM rewrite" if method == "llm_reworded" else "Deterministic fallback"))
st.write(review.get("explanation", "No explanation provided.").split("Points for the recruiter to check:")[0].strip())

st.write("**Recommended recruiter checks**")
checks = []
if not match_available:
    checks.append("Add clear mandatory or preferred requirements to the job description.")
if summary.get("extraction_confidence", 0) < 0.75:
    checks.append("Verify the CV text, experience dates, and education manually.")
checks.extend(flag.get("message", "Review the flagged issue.") for flag in review.get("risk_flags", []))
for check in dict.fromkeys(checks):
    st.warning(check)

st.write("**Risk flags**")
risk_flags = review.get("risk_flags", [])
if risk_flags:
    for flag in risk_flags:
        st.warning(
            f"{flag.get('severity', 'warning').title()}: "
            f"{flag.get('message', 'No message provided.')}"
        )
else:
    st.write("No risk flags recorded.")

st.write("**Privacy check**")
privacy_check = review.get("privacy_check", {})
if privacy_check.get("passed"):
    st.success("Passed")
else:
    st.error("Privacy check requires attention")
    violations = privacy_check.get("violations", [])
    st.write(", ".join(violations) or "No violation details provided.")