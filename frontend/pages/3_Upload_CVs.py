"""Page 3 - CV upload and pipeline activity."""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

st.title("Candidate Intelligence")
st.caption("Upload CVs to extract an anonymous, job-relevant profile.")
st.warning("Recruiter review required")

job_id = st.text_input("Job ID", value=st.session_state.get("upload_job_id", ""))

files = st.file_uploader(
    "Choose CV files",
    type=["pdf", "docx", "txt", "md"],
    accept_multiple_files=True,
    help="Files are validated, PII-redacted, parsed, and encrypted by Agent 1.",
)

uploaded_files = files or []

if st.button("Process CVs", type="primary", disabled=not uploaded_files):
    job_id = job_id.strip()
    if not job_id:
        st.error("Enter a job ID before processing CVs.")
        st.stop()
    payload = [
        ("files", (file.name, file.getvalue(), file.type or "application/octet-stream"))
        for file in uploaded_files
    ]
    with st.spinner("Agent 1 is extracting and anonymizing candidate profiles..."):
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/pipeline/run",
                data={"job_id": job_id},
                files=payload,
                timeout=120,
            )
        except requests.RequestException as exc:
            st.error(f"Could not reach the FastAPI backend: {exc}")
        else:
            if response.ok:
                results = response.json()
                st.session_state["upload_job_id"] = job_id
                st.session_state["pipeline_results"] = results
                st.success(f"Processed {len(results)} candidate(s).")
            else:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                st.error(f"The pipeline could not process the upload: {detail}")

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