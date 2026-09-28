"""Page 2 - Create a new HireWise job vacancy."""

from __future__ import annotations

import os

import requests
import streamlit as st

try:
    from frontend.auth import auth_headers, require_login
except ModuleNotFoundError:
    from auth import auth_headers, require_login


API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")


# ---------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------

require_login()


# ---------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------

st.title("💼 Create New Job")

st.write(
    "Create a new job vacancy and let HireWise analyze its "
    "requirements for Agent 2 matching."
)

st.divider()


# ---------------------------------------------------------------------
# Job creation form
# ---------------------------------------------------------------------

st.subheader("Job Details")

with st.form("create_job_form"):

    job_title = st.text_input(
        "Job Title",
        placeholder="e.g., Junior Data Analyst",
    )

    job_description = st.text_area(
        "Job Description",
        placeholder=(
            "Enter the complete job description here...\n\n"
            "Example:\n"
            "- Required skills: Python, SQL, Power BI\n"
            "- Preferred skills: Tableau\n"
            "- Minimum 1 year relevant experience\n"
            "- Bachelor's degree in IT, Data Science, or related field\n"
            "- Responsibilities: Analyze data, create dashboards, "
            "prepare reports"
        ),
        height=300,
    )

    submitted = st.form_submit_button(
        "🚀 Create Job",
        type="primary",
        use_container_width=True,
    )


# ---------------------------------------------------------------------
# Create job
# ---------------------------------------------------------------------

if submitted:

    if not job_title.strip():

        st.error("Please enter a job title.")

    elif not job_description.strip():

        st.error("Please enter a job description.")

    else:

        payload = {
            "title": job_title.strip(),
            "description": job_description.strip(),
        }

        with st.spinner("Creating job and analyzing requirements..."):

            try:

                response = requests.post(
                    f"{API_BASE_URL}/api/agent2/jobs",
                    json=payload,
                    headers=auth_headers(),
                    timeout=60,
                )

                if response.ok:

                    job = response.json()

                    # Save current job in session state
                    st.session_state["created_job"] = job
                    st.session_state["selected_job"] = job
                    st.session_state["job_id"] = job.get("job_id")

                    st.success(
                        f"Job created successfully: "
                        f"{job.get('title', job_title)}"
                    )

                else:

                    try:
                        detail = response.json().get(
                            "detail",
                            "Failed to create job.",
                        )
                    except ValueError:
                        detail = (
                            f"HTTP {response.status_code}: "
                            "Failed to create job."
                        )

                    st.error(detail)

            except requests.exceptions.ConnectionError:

                st.error(
                    "Backend is not running. "
                    "Start FastAPI before creating a job."
                )

            except requests.RequestException as exc:

                st.error(
                    f"Backend request failed: {exc}"
                )


# ---------------------------------------------------------------------
# Created job information
# ---------------------------------------------------------------------

created_job = st.session_state.get("created_job")

if created_job:

    st.divider()

    st.subheader("✅ Job Created")

    job_id = created_job.get("job_id")
    title = created_job.get(
        "title",
        created_job.get("job_title", "Untitled Job"),
    )

    st.info(
        f"**Job Title:** {title}\n\n"
        f"**Job ID:** `{job_id}`"
    )

    st.write(
        "The vacancy is now saved. You can continue to "
        "CV upload for this job."
    )

    if st.button(
        "📄 Upload CVs for this Job →",
        type="primary",
        use_container_width=True,
    ):

        st.switch_page("pages/3_Upload_CVs.py")