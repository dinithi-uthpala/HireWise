"""Audit history and audit-chain verification."""
from __future__ import annotations

import os

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
    return response.json()


st.title("Audit Log")
st.caption("Each entry contains a hash of the previous one, so editing or deleting an old entry is detected.")

job_id = render_job_selector()
if not job_id:
    st.stop()

if job_id != st.session_state.get("audit_job_id"):
    try:
        with st.spinner("Loading candidates..."):
            st.session_state["audit_candidates"] = load_candidates(job_id)
        st.session_state["audit_job_id"] = job_id
        st.session_state.pop("audit_events", None)
        st.session_state.pop("audit_loaded_candidate_id", None)
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Could not load candidates: {exc}")
        st.session_state["audit_candidates"] = []

candidates = st.session_state.get("audit_candidates", [])
if not candidates:
    st.info("No candidates were found for this job.")
else:
    candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    candidate_ids = list(candidate_by_id)
    current_candidate = st.session_state.get("selected_candidate_id") or st.session_state.get("audit_candidate_id")
    selected_candidate_id = st.selectbox(
        "Candidate",
        candidate_ids,
        index=candidate_ids.index(current_candidate) if current_candidate in candidate_ids else 0,
        format_func=lambda item: (
            f"{item} | score: {candidate_by_id[item].get('match_score', 'N/A')} | "
            f"{candidate_by_id[item].get('recommendation', 'No recommendation')}"
        ),
    )
    st.session_state["selected_candidate_id"] = selected_candidate_id
    st.session_state["audit_candidate_id"] = selected_candidate_id

    for note in candidate_by_id[selected_candidate_id].get("batch_notes", []):
        st.warning(note) if note.startswith("UNUSUAL_SCORE_PATTERN") else st.info(note)

    if selected_candidate_id != st.session_state.get("audit_loaded_candidate_id"):
        try:
            with st.spinner("Loading audit log..."):
                response = requests.get(f"{API_BASE_URL}/api/audit/{selected_candidate_id}", timeout=30)
            if not response.ok:
                st.error(response_detail(response))
                st.session_state["audit_events"] = []
            else:
                st.session_state["audit_events"] = response.json()
                st.session_state["audit_loaded_candidate_id"] = selected_candidate_id
        except requests.RequestException as exc:
            st.error(f"Could not load audit log: {exc}")

events = st.session_state.get("audit_events", [])
if candidates and not events and st.session_state.get("audit_loaded_candidate_id"):
    st.info("No audit entries were found for this candidate.")
if events:
    st.subheader(f"Audit entries: {st.session_state['audit_candidate_id']}")
    st.dataframe(
        pd.DataFrame(
            {"Time": event.get("ts", ""), "Actor": event.get("actor", ""), "Action": event.get("action", "")}
            for event in events
        ),
        use_container_width=True,
        hide_index=True,
    )
    for event in events:
        with st.expander(f"{event.get('ts', 'Unknown time')} | {event.get('action', 'Unknown action')}"):
            st.write(f"**Actor:** {event.get('actor', 'Unknown')}")
            st.json(event.get("summary", {}))

st.divider()
if st.button("Run/View Fairness Test"):
    open_page("pages/7_Fairness_Test.py")

if st.button("Verify audit log integrity"):
    try:
        with st.spinner("Verifying audit log integrity..."):
            response = requests.get(f"{API_BASE_URL}/api/audit-chain/verify", timeout=30)
        if not response.ok:
            st.error(response_detail(response))
        else:
            result = response.json()
            if result.get("valid"):
                st.success(f"Chain valid - {result.get('entries_checked', 0)} entries checked")
            else:
                st.error(f"Possible tampering detected at entry {result.get('first_bad_entry_id', 'unknown')}")
    except requests.RequestException as exc:
        st.error(f"Could not verify audit log: {exc}")
