"""Candidate detail and score explanation."""
from __future__ import annotations

import os
import time

import requests
import streamlit as st

try:
    from frontend.job_selection import open_page, render_job_selector
except ModuleNotFoundError:  # Streamlit runs pages with frontend on sys.path.
    from job_selection import open_page, render_job_selector

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


def load_candidates_with_retry(job_id: str) -> list[dict]:
    """Retry once while a just-finished pipeline result becomes visible."""

    response = requests.get(f"{API_BASE_URL}/api/jobs/{job_id}/candidates", timeout=30)
    if not response.ok:
        raise ValueError(response_detail(response))
    candidates = response.json()
    if not candidates:
        time.sleep(0.25)
        response = requests.get(f"{API_BASE_URL}/api/jobs/{job_id}/candidates", timeout=30)
        if not response.ok:
            raise ValueError(response_detail(response))
        candidates = response.json()
    return candidates


st.title("Candidate Detail")
st.caption("Review the evidence behind a candidate's matching score.")

job_id = render_job_selector()
if not job_id:
    st.stop()

selected_from_ranking = st.session_state.get("selected_candidate_id")
if (
    selected_from_ranking
    and selected_from_ranking != st.session_state.get("detail_loaded_candidate_id")
):
    st.session_state.pop("detail_data", None)
    try:
        with st.spinner("Loading selected candidate..."):
            response = requests.get(
                f"{API_BASE_URL}/api/candidates/{selected_from_ranking}", timeout=30
            )
        if response.ok:
            st.session_state["detail_data"] = response.json()
            st.session_state["detail_loaded_candidate_id"] = selected_from_ranking
        else:
            st.warning("Selected candidate is not available yet; reloading the job list.")
    except requests.RequestException as exc:
        show_backend_error(exc)

if job_id != st.session_state.get("detail_job_id") or not st.session_state.get("detail_candidates"):
    try:
        with st.spinner("Loading candidates..."):
            st.session_state["detail_candidates"] = load_candidates_with_retry(job_id)
        st.session_state["detail_job_id"] = job_id
        if not selected_from_ranking:
            st.session_state.pop("detail_loaded_candidate_id", None)
            st.session_state.pop("detail_data", None)
    except (requests.RequestException, ValueError) as exc:
        if isinstance(exc, requests.RequestException):
            show_backend_error(exc)
        else:
            st.error(str(exc))

candidates = st.session_state.get("detail_candidates", [])
if st.session_state.get("detail_job_id") and not candidates and not selected_from_ranking:
    st.info("No candidates were found for this job.")
    st.stop()

if not candidates and not selected_from_ranking:
    st.info("Enter a job ID and load candidates to view candidate details.")
    st.stop()
    # ``st.stop`` only halts an active Streamlit script. Keep ordinary imports
    # (including tooling that imports page modules) safe as well.
    candidates = [{"candidate_id": "", "match_score": None}]

candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
if selected_from_ranking and selected_from_ranking not in candidate_by_id:
    # Use the candidate-specific endpoint after Ranking -> Detail navigation
    # even when the list endpoint is briefly behind the pipeline write.
    candidate_by_id[selected_from_ranking] = {"candidate_id": selected_from_ranking}
candidate_ids = list(candidate_by_id)
selected_candidate_id = st.selectbox(
    "Candidate",
    candidate_ids,
    index=(
        candidate_ids.index(st.session_state.get("selected_candidate_id"))
        if st.session_state.get("selected_candidate_id") in candidate_ids
        else 0
    ),
    format_func=lambda candidate_id: (
        f"{candidate_id} | score: "
        f"{candidate_by_id[candidate_id].get('match_score', 'N/A')} | "
        f"{candidate_by_id[candidate_id].get('recommendation', 'No recommendation')}"
    ),
)
st.session_state["selected_candidate_id"] = selected_candidate_id
st.session_state["detail_candidate_id"] = selected_candidate_id

if (
    selected_candidate_id != st.session_state.get("detail_loaded_candidate_id")
    or not st.session_state.get("detail_data")
):
    try:
        with st.spinner("Loading candidate details..."):
            response = requests.get(
                f"{API_BASE_URL}/api/candidates/{selected_candidate_id}", timeout=30
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
left, right = st.columns(2)
left.metric("Overall score", "Not available" if score is None else f"{score:.1f}")
right.write("**Recommendation**")
right.write(summary.get("recommendation", "No recommendation provided."))

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
st.write(review.get("explanation", "No explanation provided."))

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

st.markdown("#### Human decision")
with st.form("human_decision_form"):
    decision = st.radio(
        "Decision",
        options=["shortlist", "hold", "not_selected"],
        format_func=lambda value: {
            "shortlist": "Shortlist",
            "hold": "Hold",
            "not_selected": "Not Selected",
        }[value],
        horizontal=True,
    )
    note = st.text_area("Note (optional)", max_chars=2000)
    save_decision = st.form_submit_button("Save decision", type="primary")

if save_decision:
    try:
        with st.spinner("Saving human decision..."):
            response = requests.post(
                f"{API_BASE_URL}/api/candidates/{selected_candidate_id}/decision",
                json={"decision": decision, "note": note},
                timeout=30,
            )
        if not response.ok:
            st.error(response_detail(response))
        else:
            st.success(f"Human decision saved: {decision.replace('_', ' ').title()}.")
            st.session_state["audit_candidate_id"] = selected_candidate_id
    except requests.RequestException as exc:
        show_backend_error(exc)

if st.button("Open decision audit"):
    st.session_state["audit_candidate_id"] = selected_candidate_id
    open_page("pages/6_Decision_Audit.py")
