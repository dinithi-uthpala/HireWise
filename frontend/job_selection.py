"""Shared saved-job selector for recruiter-facing Streamlit pages."""
from __future__ import annotations

import requests
import streamlit as st


def load_saved_jobs(api_base_url: str, headers: dict[str, str]) -> list[dict]:
    """Load only the curated roles exposed by the backend catalogue."""
    response = requests.get(
        f"{api_base_url}/api/agent2/jobs",
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def select_saved_job(
    api_base_url: str,
    headers: dict[str, str],
    state_key: str,
    label: str = "Select a job role",
) -> dict | None:
    """Render a role dropdown and return the selected saved job."""
    try:
        jobs = load_saved_jobs(api_base_url, headers)
    except requests.RequestException as exc:
        st.error(f"Could not load saved job roles: {exc}")
        return None

    if not jobs:
        st.error("No saved job roles are available.")
        return None

    jobs_by_title = {job["job_title"]: job for job in jobs}
    titles = list(jobs_by_title)
    previous = st.session_state.get(state_key)
    index = titles.index(previous) if previous in titles else 0
    selected_title = st.selectbox(label, titles, index=index, key=f"{state_key}_select")
    selected_job = jobs_by_title[selected_title]
    st.session_state[state_key] = selected_title

    with st.expander("View selected job description", expanded=False):
        st.write(selected_job["job_description"])
    return selected_job
