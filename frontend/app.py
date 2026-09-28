"""HireWise application entry point."""

from __future__ import annotations

import streamlit as st

try:
    from frontend.auth import is_logged_in, show_login
except ModuleNotFoundError:
    from auth import is_logged_in, show_login


st.set_page_config(
    page_title="HireWise",
    page_icon="H",
    layout="wide",
)


def login_page() -> None:
    """Render the administrator login page."""
    show_login()


# ---------------------------------------------------------
# Navigation depends on authentication state
# ---------------------------------------------------------

if not is_logged_in():
    # Before login, expose ONLY the login page.
    login_nav = st.navigation(
        [
            st.Page(
                login_page,
                title="Login",
                icon="🔐",
            )
        ]
    )
    login_nav.run()

else:
    # After successful login, expose the recruiter workflow.
    recruiter_pages = [
        st.Page(
            "pages/1_Login_Dashboard.py",
            title="Login Dashboard",
            icon="🏠",
        ),
        st.Page(
            "pages/2_Create_Job.py",
            title="Create Job",
            icon="💼",
        ),
        st.Page(
            "pages/2_Existing_Job.py",
            title="Existing Job",
            icon="📂",
        ),
        st.Page(
            "pages/3_Upload_CVs.py",
            title="Upload CVs",
            icon="📄",
        ),
        st.Page(
            "pages/4_Ranking.py",
            title="Ranking",
            icon="📊",
        ),
        st.Page(
            "pages/5_Candidate_Detail.py",
            title="Candidate Detail",
            icon="👤",
        ),
        st.Page(
            "pages/6_Decision_Audit.py",
            title="Decision Audit",
            icon="🔍",
        ),
        st.Page(
            "pages/7_Fairness_Test.py",
            title="Fairness Test",
            icon="⚖️",
        ),
    ]

    navigation = st.navigation(recruiter_pages)
    navigation.run()
