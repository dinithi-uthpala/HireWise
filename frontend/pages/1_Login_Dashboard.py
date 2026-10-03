"""Recruiter dashboard."""
import streamlit as st
try:
    from frontend.auth import require_login
    from frontend.ui import page_header
except ModuleNotFoundError:
    from auth import require_login
    from ui import page_header

require_login()
name = st.session_state.get("admin_username", "Administrator").replace("_", " ").title()
page_header(f"Welcome, {name} 👋", "Manage recruitment processes with the help of AI agents.", ":material/waving_hand:")
st.markdown("""<div class='hw-hero'><h2>Recruiter dashboard</h2><p>Start a new recruitment process or continue with an existing saved job.</p></div>""", unsafe_allow_html=True)
create, existing = st.columns(2)
with create:
    with st.container(border=True):
        st.header("Create new job", icon=":material/note_add:")
        st.write("Create a new vacancy and let HireWise analyze its requirements for candidate matching.")
        if st.button("Create new job", type="primary", width="stretch", icon=":material/arrow_forward:"):
            st.switch_page("pages/2_Create_Job.py")
with existing:
    with st.container(border=True):
        st.header("Use existing job", icon=":material/folder_open:")
        st.write("Continue recruitment for a previously created vacancy without creating another job.")
        if st.button("Use existing job", width="stretch", icon=":material/arrow_forward:"):
            st.switch_page("pages/2_Existing_Job.py")
st.info("Create a new job for a new vacancy. Use an existing job to continue uploading or reviewing CVs.", icon=":material/lightbulb:")
