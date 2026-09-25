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

score = match.get("match_score")
match_available = match.get("match_status") != "unavailable" and score is not None
score_value = f"{score:.1f}" if match_available else "N/A"

if match_available and score < 60:
    score_color = "red"
elif match_available and score < 80:
    score_color = "orange"
elif match_available:
    score_color = "green"
else:
    score_color = "gray"

recommendation = summary.get("recommendation", "No recommendation provided.")
if recommendation.lower().startswith("shortlist"):
    recommendation_color = "green"
elif recommendation.lower().startswith("hold"):
    recommendation_color = "orange"
else:
    recommendation_color = "red"

st.subheader(f"Candidate: {selected_candidate_id}")
header_left, header_score, header_rec, header_extract, header_match = st.columns(5)
with header_left:
    st.markdown("**Candidate ID**")
    st.write(selected_candidate_id)
with header_score:
    st.metric("Overall score", score_value)
with header_rec:
    st.markdown("**Recommendation**")
    st.badge(recommendation, color=recommendation_color)
with header_extract:
    st.metric("Extraction confidence", f"{summary.get('extraction_confidence', 0):.0%}")
with header_match:
    st.metric("Matching confidence", f"{review.get('matching_confidence', 0):.0%}")

risk_flags = review.get("risk_flags", [])
critical_flags = [flag for flag in risk_flags if str(flag.get("severity", "")).lower() == "critical"]
if critical_flags:
    first_critical = critical_flags[0]
    st.warning(
        f"Critical flag: {first_critical.get('code', 'RISK_FLAG')} — "
        f"{first_critical.get('message', 'No message provided.')}"
    )

if not match_available:
    st.error("No reliable match score was produced. Check the job requirements and CV extraction.")

breakdown = match.get("score_breakdown", {})
if breakdown:
    with st.expander("Score breakdown", expanded=True):
        component_labels = {
            "mandatory_skills": "Mandatory Skills",
            "experience": "Experience",
            "education": "Education",
            "preferred_skills": "Preferred Skills",
        }
        for component, label in component_labels.items():
            component_score = breakdown.get(component, 0)
            st.write(f"**{label}: {component_score:.1f}**")
            st.progress(max(0.0, min(float(component_score) / 100, 1.0)))

score_evidence = match.get("score_evidence", {})
experience_evidence = score_evidence.get("experience", {})
education_evidence = score_evidence.get("education", {})
if experience_evidence or education_evidence:
    with st.expander("Evidence", expanded=False):
        left, right = st.columns(2)
        with left:
            candidate_years = experience_evidence.get("candidate_years", 0.0)
            required_years = experience_evidence.get("required_years", 0.0)
            st.write("**Experience**")
            st.write(f"Candidate: **{candidate_years:.2f} years**")
            st.write(f"Role requirement: **{required_years:.2f} years**")
            st.write(experience_evidence.get("evidence", "No experience evidence recorded."))
        with right:
            st.write("**Education and certifications**")
            st.write(f"Candidate education: {', '.join(education_evidence.get('candidate_education', [])) or 'None extracted'}")
            st.write(f"Required education: {education_evidence.get('required_education') or 'Not specified'}")
            st.write(f"Education status: **{education_evidence.get('education_match_status', 'unknown').replace('_', ' ').title()}**")
            required_certs = education_evidence.get("required_certifications", [])
            matched_certs = education_evidence.get("matched_certifications", [])
            st.write(f"Certifications required: {', '.join(required_certs) or 'None'}")
            st.write(f"Certifications matched: {', '.join(matched_certs) or 'None'}")
            st.write(education_evidence.get("evidence", "No education evidence recorded."))

matched_mandatory = match.get("matched_mandatory_skills", [])
matched_preferred = match.get("matched_preferred_skills", [])
skill_gaps = match.get("skill_gaps", [])
if matched_mandatory or matched_preferred or skill_gaps:
    with st.expander("Skills", expanded=False):
        left, right = st.columns(2)
        if matched_mandatory or matched_preferred:
            with left:
                st.write("**Matched skills**")
                if matched_mandatory:
                    for skill in matched_mandatory:
                        st.success(f"Mandatory: {skill}")
                if matched_preferred:
                    for skill in matched_preferred:
                        st.success(f"Preferred: {skill}")
        if skill_gaps:
            with right:
                st.write("**Skill gaps**")
                for gap in skill_gaps:
                    st.warning(
                        f"{gap.get('skill', 'Unknown skill')} "
                        f"({gap.get('category', 'unknown')}): {gap.get('reason', 'No reason provided.')}"
                    )

uncertain_matches = match.get("uncertain_matches", [])
if uncertain_matches:
    with st.expander("Uncertain matches", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Requirement": item.get("requirement", ""),
                        "Reason": item.get("reason", ""),
                    }
                    for item in uncertain_matches
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

if review.get("explanation"):
    with st.expander("Full explanation", expanded=False):
        method = review.get("explanation_method", "rule_template")
        st.caption("Explanation source: " + ("Gemini LLM rewrite" if method == "llm_reworded" else "Deterministic fallback"))
        st.write(review.get("explanation", "No explanation provided.").strip())

privacy_check = review.get("privacy_check", {})
if risk_flags or privacy_check:
    with st.expander("Risk flags & privacy check", expanded=False):
        if risk_flags:
            for flag in risk_flags:
                code = flag.get("code", "RISK_FLAG")
                severity = str(flag.get("severity", "warning")).lower()
                if severity in {"critical", "high"}:
                    color = "red"
                elif severity in {"medium", "warning", "moderate"}:
                    color = "orange"
                elif severity in {"low", "info"}:
                    color = "yellow"
                else:
                    color = "gray"
                st.badge(code, color=color)
                st.write(flag.get("message", "No message provided."))
        st.write("**Privacy check**")
        if privacy_check.get("passed"):
            st.success("Passed")
        else:
            st.error("Privacy check requires attention")
            violations = privacy_check.get("violations", [])
            st.write(", ".join(violations) or "No violation details provided.")

if st.session_state.get("detail_data"):
    st.divider()
    st.page_link("pages/6_Decision_Audit.py", label="➡️ View Decision Audit")