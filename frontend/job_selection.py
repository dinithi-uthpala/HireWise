"""Shared saved-job selection helpers for Streamlit workflow pages."""
from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "HIREWISE_API_URL", os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
).rstrip("/")


def set_selected_job(job: dict[str, Any]) -> None:
    """Store one normalized saved job under the workflow-wide session keys."""

    job_id = str(job.get("job_id", "")).strip()
    if not job_id:
        return
    selected_job = {
        "job_id": job_id,
        "job_title": str(job.get("job_title") or job.get("title") or "Untitled job"),
        "job_description": str(job.get("job_description", "")),
    }
    st.session_state["selected_job"] = selected_job
    st.session_state["job_id"] = job_id


def selected_job_id() -> str:
    """Return the selected job ID, keeping legacy session keys in sync."""

    selected_job = st.session_state.get("selected_job") or {}
    job_id = str(selected_job.get("job_id") or st.session_state.get("job_id") or "")
    if job_id and not selected_job:
        st.session_state["selected_job"] = {"job_id": job_id, "job_title": "Selected job"}
    if job_id:
        st.session_state["job_id"] = job_id
    return job_id


def load_saved_jobs() -> list[dict[str, Any]]:
    """Load saved Agent 2 vacancies without raising UI-breaking exceptions."""

    response = requests.get(f"{API_BASE_URL}/api/agent2/jobs", timeout=30)
    response.raise_for_status()
    return response.json()


def render_job_selector() -> str:
    """Render the shared saved-job selector and return its selected ID."""

    try:
        jobs = load_saved_jobs()
    except requests.RequestException as exc:
        st.warning(f"Could not load saved jobs: {exc}")
        return selected_job_id()

    if not jobs:
        st.info("No saved jobs yet. Create a job before uploading or reviewing CVs.")
        return ""

    job_by_id = {job["job_id"]: job for job in jobs}
    job_ids = list(job_by_id)
    current_id = selected_job_id()
    index = job_ids.index(current_id) if current_id in job_by_id else 0
    job_id = st.selectbox(
        "Saved job",
        job_ids,
        index=index,
        format_func=lambda item: f"{job_by_id[item].get('job_title', 'Untitled job')} ({item})",
        key="selected_job_picker",
    )
    set_selected_job(job_by_id[job_id])
    return job_id


def open_page(page: str) -> None:
    """Navigate within the Streamlit multipage app when the API is available."""

    st.switch_page(page)
