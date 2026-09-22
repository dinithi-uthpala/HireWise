"""Audit history and audit-chain verification."""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

try:
    from frontend.auth import auth_headers, require_login
except ModuleNotFoundError:
    from auth import auth_headers, require_login

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


st.title("Audit Log")
st.caption(
    "Each entry contains a hash of the previous one, so editing or deleting "
    "an old entry is detected."
)

with st.form("load_candidates_form"):
    job_id = st.text_input("Job ID", value=st.session_state.get("audit_job_id", ""))
    load_candidates = st.form_submit_button("Load candidates", type="primary")

if load_candidates:
    job_id = job_id.strip()
    if not job_id:
        st.error("Enter a job ID to load candidates.")
    else:
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
                st.session_state["audit_job_id"] = job_id
                st.session_state["audit_candidates"] = response.json()
                st.session_state.pop("audit_candidate_id", None)
                st.session_state.pop("audit_events", None)
                st.session_state.pop("audit_loaded_candidate_id", None)
        except requests.RequestException as exc:
            show_backend_error(exc)

candidates = st.session_state.get("audit_candidates", [])
if st.session_state.get("audit_job_id") and not candidates:
    st.info("No candidates were found for this job.")

if candidates:
    candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    candidate_ids = list(candidate_by_id)
    selected_candidate_id = st.selectbox(
        "Candidate",
        candidate_ids,
        index=candidate_ids.index(st.session_state.get("audit_candidate_id", candidate_ids[0]))
        if st.session_state.get("audit_candidate_id") in candidate_ids
        else 0,
        format_func=lambda candidate_id: (
            f"{candidate_id} | score: "
            f"{candidate_by_id[candidate_id].get('match_score', 'N/A')} | "
            f"{candidate_by_id[candidate_id].get('recommendation', 'No recommendation')}"
        ),
    )
    st.session_state["audit_candidate_id"] = selected_candidate_id
    batch_notes = candidate_by_id[selected_candidate_id].get("batch_notes", [])
    for note in batch_notes:
        if note.startswith("UNUSUAL_SCORE_PATTERN"):
            st.warning(note)
        else:
            st.info(note)

    if selected_candidate_id != st.session_state.get("audit_loaded_candidate_id"):
        try:
            with st.spinner("Loading audit log..."):
                response = requests.get(
                    f"{API_BASE_URL}/api/audit/{selected_candidate_id}",
                    headers=auth_headers(),
                    timeout=30,
                )
            if not response.ok:
                st.error(response_detail(response))
                st.session_state["audit_events"] = []
            else:
                response.raise_for_status()
                st.session_state["audit_events"] = response.json()
                st.session_state["audit_loaded_candidate_id"] = selected_candidate_id
        except requests.RequestException as exc:
            show_backend_error(exc)

events = st.session_state.get("audit_events", [])
if candidates and not events and st.session_state.get("audit_loaded_candidate_id"):
    st.info("No audit entries were found for this candidate.")

if events:
    st.subheader(f"Audit entries: {st.session_state['audit_candidate_id']}")
    event_rows = [
        {
            "Time": event.get("ts", ""),
            "Actor": event.get("actor", ""),
            "Action": event.get("action", ""),
        }
        for event in events
    ]
    st.dataframe(pd.DataFrame(event_rows), use_container_width=True, hide_index=True)

    st.subheader("Entry details")
    for event in events:
        label = f"{event.get('ts', 'Unknown time')} | {event.get('action', 'Unknown action')}"
        with st.expander(label):
            st.write(f"**Actor:** {event.get('actor', 'Unknown')}")
            st.json(event.get("summary", {}))

st.divider()
if st.button("Verify audit log integrity"):
    try:
        with st.spinner("Verifying audit log integrity..."):
            response = requests.get(
                f"{API_BASE_URL}/api/audit-chain/verify",
                headers=auth_headers(),
                timeout=30,
            )
        if not response.ok:
            st.error(response_detail(response))
        else:
            response.raise_for_status()
            result = response.json()
            if result.get("valid"):
                st.success(f"Chain valid - {result.get('entries_checked', 0)} entries checked")
            else:
                bad_id = result.get("first_bad_entry_id", "unknown")
                st.error(f"Possible tampering detected at entry {bad_id}")
    except requests.RequestException as exc:
        show_backend_error(exc)