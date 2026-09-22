"""Page 1 - Administrator login and dashboard."""
import streamlit as st

try:
    from frontend.auth import show_login, show_logout
except ModuleNotFoundError:
    from auth import show_login, show_logout

if show_login():
    show_logout()
    st.title("Recruiter Dashboard")
    st.success("Administrator authenticated.")
    st.warning("Recruiter review required")