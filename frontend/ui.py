"""Shared presentation helpers for the HireWise Streamlit workflow."""
from __future__ import annotations

import streamlit as st


def apply_branding() -> None:
    st.html("""<style>
    .stApp{background:#f5f7fc;color:#101b33}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#101b33,#14213d)}
    [data-testid="stSidebar"] *{color:#eef3ff}
    [data-testid="stSidebar"] [aria-current="page"]{background:linear-gradient(90deg,#6c3bff,#2583e8);border-radius:10px}
    [data-testid="stSidebar"] [data-testid="stSidebarNav"]{padding-top:2rem}
    [data-testid="stSidebar"] [data-testid="stSidebarNav"] a{font-size:1.08rem;font-weight:500}
    .hw-sidebar-brand{position:fixed;top:.85rem;z-index:20;font-size:1.35rem;font-weight:800;color:#eef3ff}
    [data-testid="stSidebar"] [data-testid="stButton"] button{position:fixed;bottom:1rem;left:1rem;width:18rem;background:#14213d;border:1px solid rgba(255,255,255,.42);color:#fff;z-index:20}
    [data-testid="stForm"],[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:16px;border-color:#e4e9f5;box-shadow:0 8px 24px rgba(16,27,51,.05)}
    .hw-brand{font-size:1.3rem;font-weight:750;color:#101b33}.hw-eyebrow{color:#6246ea;font-size:.79rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase}.hw-hero{padding:1.5rem 1.75rem;border-radius:18px;background:linear-gradient(105deg,#e9efff,#f3ecff);border:1px solid #dce5fb;margin:.25rem 0 1.25rem}.hw-hero h2{margin:0 0 .35rem;color:#101b33}.hw-hero p{margin:0;color:#405577}.hw-login-title{font-size:2.5rem;line-height:1.08;font-weight:800;letter-spacing:-.04em;color:#101b33;margin:1.15rem 0 .8rem}.hw-login-title span{color:#6940f3}.hw-login-feature{padding:.45rem 0;color:#23395d;font-weight:600}div.stButton>button[kind="primary"]{background:linear-gradient(90deg,#6c3bff,#2583e8);border:0}div.stButton>button{border-radius:9px;font-weight:650}[data-testid="stMetric"]{background:#fff;border:1px solid #e4e9f5;border-radius:14px;padding:.75rem}</style>""")


def sidebar_brand() -> None:
    with st.sidebar:
        st.markdown("<div class='hw-sidebar-brand'>👥 HireWise</div>", unsafe_allow_html=True)


def page_header(title: str, subtitle: str, icon: str = "") -> None:
    st.markdown("<div class='hw-eyebrow'>HireWise workspace</div>", unsafe_allow_html=True)
    st.title(title, icon=icon or None)
    st.caption(subtitle)


def selected_job_card() -> None:
    job = st.session_state.get("selected_job") or {}
    job_id = job.get("job_id") or st.session_state.get("job_id")
    if job_id:
        with st.container(border=True):
            st.caption("Selected job")
            st.markdown(f"**{job.get('job_title') or job.get('title') or 'Selected job'}**")
            st.caption(f"Job ID: {job_id}")


def skill_list(label: str, skills: list[str], color: str = "green") -> None:
    st.markdown(f"**{label}**")
    st.markdown(" ".join(f":{color}-badge[{skill}]" for skill in skills) if skills else "None recorded")
