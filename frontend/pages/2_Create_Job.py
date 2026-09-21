"""
HireWise - Create Job

Creates and persists a job through the Agent 2 API,
then displays the extracted job requirement analysis.
"""

import os

import requests
import streamlit as st


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

API_BASE_URL = os.getenv(
    "HIREWISE_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

CREATE_JOB_URL = f"{API_BASE_URL}/api/agent2/jobs"


def response_error(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    return str(detail or f"HTTP {response.status_code}")


# ---------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="HireWise - Create Job",
    page_icon="💼",
    layout="wide",
)


# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------

if "created_job" not in st.session_state:
    st.session_state["created_job"] = None

if "job_requirements" not in st.session_state:
    st.session_state["job_requirements"] = None


# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------

st.title("💼 Create Job")

st.write(
    "Create a job vacancy and let HireWise analyze its requirements "
    "for Agent 2 matching."
)

st.divider()


# ---------------------------------------------------------------------
# Job creation form
# ---------------------------------------------------------------------

with st.form("create_job_form"):

    st.subheader("Job Details")

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
            "- Bachelor's degree in IT, Data Science, or related field"
        ),
        height=300,
    )

    submitted = st.form_submit_button(
        "🚀 Create Job",
        use_container_width=True,
    )


# ---------------------------------------------------------------------
# Submit job
# ---------------------------------------------------------------------

if submitted:

    # ---------------------------------------------------------------
    # Basic frontend validation
    # ---------------------------------------------------------------

    if not job_title.strip():

        st.error("Please enter a job title.")

    elif not job_description.strip():

        st.error("Please enter a job description.")

    else:

        payload = {
            "job_title": job_title.strip(),
            "job_description": job_description.strip(),
        }

        try:

            # -------------------------------------------------------
            # Create job
            # -------------------------------------------------------

            with st.spinner("Creating job..."):

                response = requests.post(
                    CREATE_JOB_URL,
                    json=payload,
                    timeout=30,
                )

            # -------------------------------------------------------
            # Successful creation
            # -------------------------------------------------------

            if response.status_code in (200, 201):

                created_job = response.json()

                # Store created job.
                st.session_state["created_job"] = created_job

                # Store Job ID separately.
                job_id = created_job.get("job_id")

                st.session_state["job_id"] = job_id

                # Reset previous requirement analysis.
                st.session_state["job_requirements"] = None

                st.success(
                    "Job created successfully! 🎉"
                )

                # ---------------------------------------------------
                # Get requirement analysis
                # ---------------------------------------------------

                if job_id:

                    requirements_url = (
                        f"{API_BASE_URL}"
                        f"/api/agent2/jobs/{job_id}/requirements"
                    )

                    try:

                        with st.spinner(
                            "Analyzing job requirements..."
                        ):

                            requirements_response = requests.get(
                                requirements_url,
                                timeout=30,
                            )

                        if requirements_response.status_code == 200:

                            requirements_data = (
                                requirements_response.json()
                            )

                            st.session_state[
                                "job_requirements"
                            ] = requirements_data

                            st.success(
                                "Requirement analysis completed! "
                                "✅"
                            )

                        else:

                            st.warning(
                                "Job was created successfully, "
                                "but requirement analysis could "
                                "not be completed."
                            )

                            requirement_error = response_error(
                                requirements_response
                            )

                            with st.expander(
                                "Requirement Analysis API Details"
                            ):
                                st.write(requirement_error)

                    except requests.exceptions.ConnectionError:

                        st.warning(
                            "Backend is not running. Start it with: "
                            "uvicorn backend.main:app --reload --port 8000"
                        )

                    except requests.exceptions.Timeout:

                        st.warning(
                            "Job was created, but requirement analysis "
                            "timed out."
                        )

                    except requests.exceptions.RequestException as exc:

                        st.warning(
                            "Job was created, but an error occurred "
                            f"during requirement analysis: {exc}"
                        )

            # ---------------------------------------------------------
            # Duplicate Job ID
            # ---------------------------------------------------------

            elif response.status_code == 409:

                st.error(
                    f"{response_error(response)}. Please try again."
                )

            # ---------------------------------------------------------
            # Other API errors
            # ---------------------------------------------------------

            else:

                st.error(
                    f"Failed to create job "
                    f"({response_error(response)})."
                )

                with st.expander("API Error Details"):
                    st.write(response_error(response))

        # -------------------------------------------------------------
        # Backend connection error
        # -------------------------------------------------------------

        except requests.exceptions.ConnectionError:

            st.error(
                "Backend is not running. Start it with: "
                "uvicorn backend.main:app --reload --port 8000"
            )

        # -------------------------------------------------------------
        # Timeout
        # -------------------------------------------------------------

        except requests.exceptions.Timeout:

            st.error(
                "The backend request timed out. "
                "Please try again."
            )

        # -------------------------------------------------------------
        # Other request error
        # -------------------------------------------------------------

        except requests.exceptions.RequestException as exc:

            st.error(
                f"An unexpected API error occurred: {exc}"
            )


# ---------------------------------------------------------------------
# Display created job
# ---------------------------------------------------------------------

created_job = st.session_state.get("created_job")

if created_job:

    st.divider()

    st.subheader("✅ Job Created")

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("### Job ID")

        job_id = created_job.get(
            "job_id",
            "N/A",
        )

        st.code(
            job_id,
            language="text",
        )

        st.caption(
            "Use this Job ID when matching candidates "
            "against this vacancy."
        )

    with col2:

        st.markdown("### Job Title")

        st.info(
            created_job.get(
                "job_title",
                job_title,
            )
        )

    st.markdown("### Job Description")

    st.text_area(
        "Saved description",
        value=created_job.get(
            "job_description",
            job_description,
        ),
        height=220,
        disabled=True,
    )


# ---------------------------------------------------------------------
# Requirement Analysis
# ---------------------------------------------------------------------

job_requirements_data = st.session_state.get(
    "job_requirements"
)

if job_requirements_data:

    requirements = job_requirements_data.get(
        "requirements",
        {},
    )

    warnings = job_requirements_data.get(
        "warnings",
        [],
    )

    st.divider()

    st.subheader("🔎 Requirement Analysis")

    st.write(
        "Agent 2 extracted the following structured "
        "requirements from the job description."
    )

    # -----------------------------------------------------------------
    # Skills
    # -----------------------------------------------------------------

    skill_col1, skill_col2 = st.columns(2)

    with skill_col1:

        st.markdown("### 🔴 Mandatory Skills")

        mandatory_skills = requirements.get(
            "mandatory_skills",
            [],
        )

        if mandatory_skills:

            for skill in mandatory_skills:
                st.markdown(f"- **{skill}**")

        else:

            st.info("No mandatory skills identified.")

    with skill_col2:

        st.markdown("### 🟡 Preferred Skills")

        preferred_skills = requirements.get(
            "preferred_skills",
            [],
        )

        if preferred_skills:

            for skill in preferred_skills:
                st.markdown(f"- **{skill}**")

        else:

            st.info("No preferred skills identified.")

    st.divider()

    # -----------------------------------------------------------------
    # Experience and education
    # -----------------------------------------------------------------

    info_col1, info_col2 = st.columns(2)

    with info_col1:

        st.markdown("### 💼 Minimum Experience")

        experience = requirements.get(
            "minimum_experience_years"
        )

        if experience is not None:

            # Display "1 year" for one year,
            # and "2 years", "3 years", etc. for multiple years.
            experience_label = (
                "year" if experience == 1 else "years"
            )

            st.metric(
                "Required Experience",
                f"{experience:g} {experience_label}",
            )

        else:

            st.info(
                "No minimum experience requirement identified."
            )

    with info_col2:

        st.markdown("### 🎓 Required Education")

        education = requirements.get(
            "required_education_level"
        )

        if education:

            st.info(
                str(education).replace(
                    "_",
                    " ",
                ).title()
            )

        else:

            st.info(
                "No specific education requirement identified."
            )

    # -----------------------------------------------------------------
    # Responsibilities
    # -----------------------------------------------------------------

    responsibilities = requirements.get(
        "responsibilities",
        [],
    )

    if responsibilities:

        st.divider()

        st.markdown("### 📋 Key Responsibilities")

        for responsibility in responsibilities:

            st.markdown(
                f"- {responsibility}"
            )

    # -----------------------------------------------------------------
    # Certifications
    # -----------------------------------------------------------------

    certifications = requirements.get(
        "required_certifications",
        [],
    )

    if certifications:

        st.divider()

        st.markdown(
            "### 📜 Required Certifications"
        )

        for certification in certifications:

            st.markdown(
                f"- **{certification}**"
            )

    # -----------------------------------------------------------------
    # Warnings
    # -----------------------------------------------------------------

    if warnings:

        st.divider()

        st.warning(
            "⚠️ Agent 2 generated the following warnings:"
        )

        for warning in warnings:

            st.markdown(
                f"- {warning}"
            )

    else:

        st.success(
            "No requirement extraction warnings."
        )


# ---------------------------------------------------------------------
# Current job session information
# ---------------------------------------------------------------------

if st.session_state.get("job_id"):

    st.divider()

    st.caption(
        f"Current Job ID: "
        f"{st.session_state['job_id']}"
    )