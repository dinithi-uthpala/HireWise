"""Page 3 - CV upload and pipeline activity."""
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


def load_processed_candidates(job_id: str) -> list[dict]:
    """Read persisted pipeline results for one job from the existing API."""

    response = requests.get(f"{API_BASE_URL}/api/jobs/{job_id}/candidates", timeout=30)
    if not response.ok:
        raise ValueError(response_detail(response))
    return response.json()

st.title("Candidate Intelligence")
st.caption("Upload CVs to extract an anonymous, job-relevant profile.")
st.warning("Recruiter review required")

job_id = render_job_selector()

if job_id:
    try:
        persisted_candidates = load_processed_candidates(job_id)
        st.session_state.setdefault("upload_candidates_by_job", {})[job_id] = persisted_candidates
    except (requests.RequestException, ValueError) as exc:
        persisted_candidates = st.session_state.get("upload_candidates_by_job", {}).get(job_id, [])
        st.error(f"Unable to load processed candidates: {exc}")
else:
    persisted_candidates = []

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
        st.error("Select a saved job before processing CVs.")
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
                st.session_state["job_id"] = job_id
                st.session_state["pipeline_results"] = results
                st.session_state.setdefault("pipeline_results_by_job", {})[job_id] = results
                try:
                    persisted_candidates = load_processed_candidates(job_id)
                    st.session_state.setdefault("upload_candidates_by_job", {})[job_id] = persisted_candidates
                    # Replace any stale empty Ranking cache for this same job.
                    st.session_state["results_job_id"] = job_id
                    st.session_state["candidate_results"] = persisted_candidates
                except (requests.RequestException, ValueError) as exc:
                    st.warning(f"CVs were processed, but results could not be reloaded: {exc}")
                processed_candidates = [
                    item.get("candidate") for item in results if item.get("candidate")
                ]
                if processed_candidates:
                    st.session_state["selected_candidate_id"] = processed_candidates[0]["candidate_id"]
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

results = st.session_state.get("pipeline_results_by_job", {}).get(job_id, [])
if not results and persisted_candidates:
    # Filenames are deliberately not persisted because they can contain PII.
    results = [
        {"filename": "Previously processed candidate", "status": "processed", "candidate": candidate}
        for candidate in persisted_candidates
    ]
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

    if st.button("View ranking for this job", type="primary"):
        open_page("pages/4_Ranking.py")
