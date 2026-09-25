"""Page 3 - CV upload and pipeline activity."""
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

st.title("Candidate Intelligence")
st.caption("Upload CVs to extract an anonymous, job-relevant profile.")
st.warning("Recruiter review required")

try:
    status_response = requests.get(
        f"{API_BASE_URL}/api/agent1/status",
        headers=auth_headers(),
        timeout=10,
    )
    if status_response.ok:
        status_data = status_response.json()
        mode = status_data.get("extraction_mode", "deterministic_fallback")
        if mode == "llm_configured":
            provider = status_data.get("llm_provider", "llm")
            st.success(f"{provider.title()} configured (deterministic fallback remains enabled)")
        else:
            st.info("Deterministic extraction fallback active; CV processing remains available.")
except requests.RequestException:
    st.warning("Agent status is unavailable; processing may still continue.")

jobs: list[dict] = []
try:
    jobs_response = requests.get(
        f"{API_BASE_URL}/api/agent2/jobs",
        headers=auth_headers(),
        timeout=15,
    )
    if jobs_response.ok:
        jobs = jobs_response.json()
    else:
        st.error("The saved job library could not be loaded.")
except requests.RequestException:
    st.error("Backend is not running. Start FastAPI before selecting a job.")

if not jobs:
    st.stop()

job_options = {job["job_title"]: job for job in jobs}
selected_title = st.selectbox(
    "Select a job role",
    list(job_options),
    index=(
        list(job_options).index(st.session_state["upload_job_title"])
        if st.session_state.get("upload_job_title") in job_options
        else 0
    ),
)
selected_job = job_options[selected_title]
job_id = selected_job["job_id"]
st.session_state["upload_job_id"] = job_id
st.session_state["upload_job_title"] = selected_title
with st.expander("View selected job description", expanded=True):
    st.write(selected_job["job_description"])

upload_mode = st.radio(
    "Candidate upload mode",
    ["Single candidate", "Multiple candidates"],
    horizontal=True,
    help="Use Multiple candidates to upload and process a batch of CVs for the same job.",
)
multiple_candidates = upload_mode == "Multiple candidates"

files = st.file_uploader(
    "Choose candidate CV files",
    type=["pdf", "docx", "txt", "md"],
    accept_multiple_files=multiple_candidates,
    help="Files are validated, PII-redacted, parsed, and encrypted by Agent 1.",
)

if multiple_candidates:
    uploaded_files = list(files or [])
else:
    uploaded_files = [files] if files is not None else []

if multiple_candidates:
    st.caption("Batch mode: all selected CVs will be matched against the same Job ID.")
if uploaded_files:
    st.success(f"{len(uploaded_files)} candidate CV(s) selected")
    st.dataframe(
        pd.DataFrame(
            [{"File": file.name, "Size (KB)": round(len(file.getvalue()) / 1024, 1)} for file in uploaded_files]
        ),
        use_container_width=True,
        hide_index=True,
    )

process_label = "Process candidate batch" if multiple_candidates else "Process candidate CV"
if st.button(process_label, type="primary", disabled=not uploaded_files):
    job_id = job_id.strip()
    payload = [
        ("files", (file.name, file.getvalue(), file.type or "application/octet-stream"))
        for file in uploaded_files
    ]
    with st.spinner("Processing CVs through Agents 1, 2, and 3..."):
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/pipeline/run",
                data={"job_id": job_id},
                files=payload,
                headers=auth_headers(),
                timeout=120,
            )
        except requests.exceptions.ConnectionError:
            st.error(
                "Backend is not running. Start it with: "
                "uvicorn backend.main:app --reload --port 8000"
            )
        except requests.RequestException as exc:
            st.error(f"Backend request failed: {exc}")
        else:
            if response.ok:
                results = response.json()
                st.session_state["upload_job_id"] = job_id
                st.session_state["pipeline_results"] = results
                st.success(f"Processed {len(results)} candidate(s).")
            else:
                try:
                    detail = response.json().get("detail")
                except ValueError:
                    detail = None
                st.error(
                    "The pipeline could not process the upload: "
                    f"{detail or f'HTTP {response.status_code}'}"
                )

results = st.session_state.get("pipeline_results", [])
if results:
    st.subheader("Agent activity")
    rows = []
    for result in results:
        candidate = result.get("candidate") or {}
        rows.append(
            {
                "File": result.get("filename", ""),
                "Candidate": candidate.get("candidate_id", "Not created"),
                "Status": result.get("status", "").title(),
                "Score": candidate.get("match_score", "N/A"),
                "Recommendation": candidate.get("recommendation", ""),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    for result in results:
        succeeded = result.get("status") == "processed"
        label = f"{result.get('filename', 'Uploaded CV')} | {result.get('status', 'unknown').title()}"
        with st.expander(label):
            activity = st.columns(3)
            for column, step in zip(
                activity,
                ("Agent 1 extracted", "Agent 2 scored", "Agent 3 reviewed"),
            ):
                if succeeded:
                    column.success(f"Done\n\n{step}")
                else:
                    column.error(f"Failed\n\n{step}")
            if not succeeded and result.get("error"):
                st.error(result["error"])
            if result.get("activity"):
                st.write("**Agent activity**")
                for step in result["activity"]:
                    st.success(step)
            if succeeded and candidate.get("match_score") is not None:
                confidence = candidate.get("extraction_confidence", 0.0)
                if confidence < 0.75 or candidate.get("status") == "awaiting_human_review":
                    st.warning("Manual review required before any recruiter decision.")

    if all(result.get("status") == "processed" for result in results):
        st.divider()
        st.page_link("pages/4_Ranking.py", label="➡️ View Ranking")