"""HireWise Recruiter Dashboard entry point."""
from __future__ import annotations

import os

import streamlit as st

try:
    from frontend.auth import show_login, show_logout
except ModuleNotFoundError:
    from auth import show_login, show_logout

st.set_page_config(page_title="HireWise", page_icon="H", layout="wide")
if show_login():
    show_logout()
    st.title("HireWise")
    st.caption("AI-assisted recruitment workspace")
    st.info("Use the pages in the sidebar to manage jobs and review candidates.")
    st.session_state.setdefault("agent1_results", [])
    st.metric("Processed candidates", len(st.session_state["agent1_results"]))
    st.caption(f"Backend URL: {os.getenv('API_BASE_URL', 'http://127.0.0.1:8000')}")