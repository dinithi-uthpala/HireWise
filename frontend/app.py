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
    pipeline_results = st.session_state.get("pipeline_results", [])
    processed_candidates = sum(
        1 for item in pipeline_results if item.get("status") == "processed"
    )
    if not pipeline_results:
        processed_candidates = len(st.session_state["agent1_results"])
    st.metric("Processed candidates", processed_candidates)
    if processed_candidates == 0:
        st.caption("No candidates processed yet. Create a job, then upload CVs.")
    st.caption(f"Backend URL: {os.getenv('API_BASE_URL', 'http://127.0.0.1:8000')}")