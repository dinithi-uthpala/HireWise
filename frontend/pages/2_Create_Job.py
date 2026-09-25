"""Page 2 - Create a job and inspect the extracted requirements."""
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


def load_saved_jobs() -> list[dict]:
    """Load the saved jobs list and cache it for reruns."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/agent2/jobs",
            headers=auth_headers(),
            timeout=15,
        )
        if response.ok:
            jobs = response.json()
            st.session_state["jobs_catalog"] = jobs
            return jobs
        st.session_state["jobs_catalog"] = []
        return []
    except requests.exceptions.ConnectionError:
        st.session_state["jobs_catalog"] = []
        st.error("Backend is not running. Start it with: uvicorn backend.main:app --reload --port 8000")
        return []
    except requests.RequestException as exc:
        st.session_state["jobs_catalog"] = []
        st.error(f"Could not load saved jobs: {exc}")
        return []


st.title("Create Job")
st.caption("Create a vacancy and extract Agent 2 requirements before uploading CVs.")
st.warning("Recruiter review required")

jobs = st.session_state.get("jobs_catalog")
if jobs is None:
    jobs = load_saved_jobs()
    st.session_state["jobs_catalog"] = jobs

with st.form("create_job_form"):
    job_title = st.text_input("Job title", placeholder="Senior Data Analyst")
    job_description = st.text_area(
        "Job description",
        height=220,
        help=(
            "Write clear mandatory skills, preferred skills, minimum experience, "
            "education, certifications, and responsibilities for the role."
        ),
        placeholder=(
            "Mandatory skills: Python, SQL, statistics\n"
            "Preferred skills: Tableau, Power BI\n"
            "Minimum 3 years of experience in analytics\n"
            "Bachelor's degree in a quantitative field\n"
            "Required certifications: Google Data Analytics\n"
            "Responsibilities: build dashboards, clean data, support reporting"
        ),
    )
    custom_job_id = st.text_input(
        "Custom job ID (optional)",
        key="custom_job_id",
        placeholder="JOB-ANALYST-01",
    )
    submitted = st.form_submit_button("Create job", type="primary")

if submitted:
    if not job_title.strip() or not job_description.strip():
        st.error("Job title and job description are required.")
    else:
        custom_id_value = (st.session_state.get("custom_job_id") or "").strip()
        payload = {
            "job_id": custom_id_value or None,
            "job_title": job_title.strip(),
            "job_description": job_description.strip(),
        }
        with st.spinner("Creating job..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/agent2/jobs",
                    json=payload,
                    headers=auth_headers(),
                    timeout=15,
                )
            except requests.exceptions.ConnectionError:
                st.error("Backend is not running. Start it with: uvicorn backend.main:app --reload --port 8000")
            except requests.RequestException as exc:
                st.error(f"Backend request failed: {exc}")
            else:
                if response.status_code == 201:
                    created_job = response.json()
                    created_job_id = created_job.get("job_id")
                    st.session_state["created_job_id"] = created_job_id
                    st.success(f"Created job '{created_job_id}'.")

                    jobs = load_saved_jobs()
                    st.session_state["jobs_catalog"] = jobs

                    requirements_url = f"{API_BASE_URL}/api/agent2/jobs/{created_job_id}/requirements"
                    try:
                        requirements_response = requests.get(
                            requirements_url,
                            headers=auth_headers(),
                            timeout=15,
                        )
                    except requests.exceptions.ConnectionError:
                        st.error("Backend is not running. Start it with: uvicorn backend.main:app --reload --port 8000")
                    except requests.RequestException as exc:
                        st.error(f"Failed to load requirements: {exc}")
                    else:
                        if requirements_response.ok:
                            extracted = requirements_response.json()
                            st.session_state["last_job_requirements"] = extracted
                            requirements = extracted.get("requirements", {})
                            warnings = extracted.get("warnings", [])

                            st.subheader("Extracted requirements")
                            for field_name, label in [
                                ("mandatory_skills", "mandatory skills"),
                                ("preferred_skills", "preferred skills"),
                                ("minimum_experience_years", "minimum_experience_years"),
                                ("required_education_level", "required_education_level"),
                                ("required_certifications", "required_certifications"),
                                ("responsibilities", "responsibilities"),
                            ]:
                                value = requirements.get(field_name)
                                if isinstance(value, list):
                                    if value:
                                        st.write(f"**{field_name}** ({label}): {', '.join(value)}")
                                    else:
                                        st.write(f"**{field_name}** ({label}): []")
                                elif value in (None, ""):
                                    st.write(f"**{field_name}** ({label}): None")
                                else:
                                    st.write(f"**{field_name}** ({label}): {value}")

                            if warnings:
                                st.subheader("Warnings")
                                for warning in warnings:
                                    st.warning(warning)

                            st.divider()
                            st.page_link("pages/3_Upload_CVs.py", label="➡️ Continue to Upload CVs")
                        else:
                            try:
                                detail = requirements_response.json().get("detail")
                            except ValueError:
                                detail = None
                            st.error(detail or f"HTTP {requirements_response.status_code}")
                elif response.status_code == 409:
                    st.error("A job with this ID already exists.")
                else:
                    try:
                        detail = response.json().get("detail")
                    except ValueError:
                        detail = None
                    st.error(detail or f"HTTP {response.status_code}")

jobs = st.session_state.get("jobs_catalog")
if jobs is None:
    jobs = load_saved_jobs()
    st.session_state["jobs_catalog"] = jobs

if jobs:
    st.subheader("Existing jobs")
    table = pd.DataFrame(
        [{"job_id": job.get("job_id", ""), "job_title": job.get("job_title", "")} for job in jobs]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
else:
    st.info("No saved jobs are available yet.")
