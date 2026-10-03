"""HireWise application entry point."""
from __future__ import annotations
import streamlit as st
try:
    from frontend.auth import is_logged_in, show_login
    from frontend.ui import apply_branding, sidebar_brand
except ModuleNotFoundError:
    from auth import is_logged_in, show_login
    from ui import apply_branding, sidebar_brand

st.set_page_config(page_title="HireWise", page_icon="👥", layout="wide")
apply_branding()

def login_page() -> None:
    show_login()

if not is_logged_in():
    st.navigation([st.Page(login_page, title="Login", icon=":material/login:")]).run()
else:
    sidebar_brand()
    pages = [
        st.Page("pages/1_Login_Dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        st.Page("pages/2_Create_Job.py", title="Create Job", icon=":material/work:"),
        st.Page("pages/2_Existing_Job.py", title="Existing Job", icon=":material/folder_open:"),
        st.Page("pages/3_Upload_CVs.py", title="Upload CVs", icon=":material/upload_file:"),
        st.Page("pages/4_Ranking.py", title="Ranking", icon=":material/leaderboard:"),
        st.Page("pages/5_Candidate_Detail.py", title="Candidate Detail", icon=":material/person_search:"),
        st.Page("pages/6_Decision_Audit.py", title="Decision Audit", icon=":material/manage_search:"),
        st.Page("pages/7_Fairness_Test.py", title="Fairness Test", icon=":material/balance:"),
    ]
    st.navigation(pages).run()
