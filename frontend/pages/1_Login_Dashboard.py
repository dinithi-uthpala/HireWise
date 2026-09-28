"""Page 1 - Administrator login and recruiter dashboard."""

import streamlit as st

try:
    from frontend.auth import show_login, show_logout
except ModuleNotFoundError:
    from auth import show_login, show_logout


# ---------------------------------------------------------------------
# Administrator login
# ---------------------------------------------------------------------

if show_login():

    show_logout()

    st.title("Recruiter Dashboard")

    st.success("Administrator authenticated.")

    st.warning("Recruiter review required")

    st.divider()

    st.subheader("What would you like to do?")

    st.write(
        "Start a new recruitment process or continue with an existing "
        "saved job."
    )

    st.write("")

    # -----------------------------------------------------------------
    # Main actions
    # -----------------------------------------------------------------

    col1, col2 = st.columns(2)

    # ================================================================
    # CREATE NEW JOB
    # ================================================================

    with col1:

        st.markdown("### ➕ Create New Job")

        st.write(
            "Create a new vacancy and let HireWise analyze its "
            "requirements for candidate matching."
        )

        if st.button(
            "Create New Job →",
            type="primary",
            use_container_width=True,
            key="create_new_job",
        ):

            st.switch_page("pages/2_Create_Job.py")

    # ================================================================
    # EXISTING JOB
    # ================================================================

    with col2:

        st.markdown("### 📂 Use Existing Job")

        st.write(
            "Continue recruitment for a previously created vacancy "
            "without creating another job."
        )

        if st.button(
            "Use Existing Job →",
            use_container_width=True,
            key="use_existing_job",
        ):

            st.switch_page("pages/2_Existing_Job.py")

    st.divider()

    st.info(
        "💡 **Tip:** Create a new job when opening a new vacancy. "
        "Use an existing job when you already have a saved vacancy "
        "and want to continue uploading or reviewing CVs."
    )