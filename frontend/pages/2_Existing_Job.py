"""Page 2 - Continue recruitment using an existing saved job."""

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

st.title("📂 Use Existing Job")

st.write(
    "Select a previously saved vacancy and continue the "
    "recruitment process without creating another job."
)

st.divider()


# ---------------------------------------------------------------------
# Load saved jobs
# ---------------------------------------------------------------------

def load_saved_jobs() -> list[dict]:
    """Load persisted jobs from Agent 2."""

    response = requests.get(
        f"{API_BASE_URL}/api/agent2/jobs",
        headers=auth_headers(),
        timeout=30,
    )

    if not response.ok:
        try:
            detail = response.json().get(
                "detail",
                "Failed to load saved jobs.",
            )
        except ValueError:
            detail = f"HTTP {response.status_code}"

        raise RuntimeError(detail)

    data = response.json()

    # Support either a direct list or common wrapped response formats.
    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        if isinstance(data.get("jobs"), list):
            return data["jobs"]

        if isinstance(data.get("items"), list):
            return data["items"]

    return []


# ---------------------------------------------------------------------
# Existing jobs
# ---------------------------------------------------------------------

try:

    existing_jobs = load_saved_jobs()

except requests.exceptions.ConnectionError:

    st.error(
        "Backend is not running. "
        "Start FastAPI before loading saved jobs."
    )

    st.stop()

except requests.RequestException as exc:

    st.error(
        f"Failed to load saved jobs: {exc}"
    )

    st.stop()

except RuntimeError as exc:

    st.error(str(exc))

    st.stop()


# ---------------------------------------------------------------------
# Display jobs
# ---------------------------------------------------------------------

if not existing_jobs:

    st.info(
        "No saved jobs are available yet. "
        "Create a new job first."
    )

    st.divider()

    if st.button(
        "➕ Create New Job",
        type="primary",
        use_container_width=True,
    ):

        st.switch_page("pages/2_Create_Job.py")

else:

    st.subheader("Select an Existing Job")

    job_options = {}

    for job in existing_jobs:

        job_id = job.get("job_id", "UNKNOWN")

        job_title = job.get(
            "title",
            job.get(
                "job_title",
                "Untitled Job",
            ),
        )

        label = f"{job_title} ({job_id})"

        job_options[label] = job

    selected_label = st.selectbox(
        "Saved jobs",
        list(job_options.keys()),
        key="existing_job_selector",
    )

    selected_job = job_options[selected_label]

    # ---------------------------------------------------------------
    # Selected job details
    # ---------------------------------------------------------------

    st.divider()

    st.subheader("Selected Job")

    job_title = selected_job.get(
        "title",
        selected_job.get(
            "job_title",
            "Untitled Job",
        ),
    )

    job_id = selected_job.get(
        "job_id",
        "N/A",
    )

    st.info(
        f"**Job Title:** {job_title}\n\n"
        f"**Job ID:** `{job_id}`"
    )

    description = selected_job.get(
        "description",
        selected_job.get(
            "job_description",
            "",
        ),
    )

    if description:

        with st.expander(
            "View Job Description",
            expanded=False,
        ):

            st.write(description)

    st.divider()

    # ---------------------------------------------------------------
    # Continue button
    # ---------------------------------------------------------------

    if st.button(
        "📄 Continue to Upload CVs →",
        type="primary",
        use_container_width=True,
    ):

        # Keep the selected job available to all following pages.
        st.session_state["selected_job"] = selected_job
        st.session_state["created_job"] = selected_job
        st.session_state["job_id"] = job_id

        # Clear candidate-specific selection from an old workflow.
        st.session_state.pop(
            "selected_candidate_id",
            None,
        )

        st.success(
            f"Using existing job: {job_title}"
        )

        st.switch_page(
            "pages/3_Upload_CVs.py"
        )
