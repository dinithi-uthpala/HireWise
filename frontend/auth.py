"""Shared Streamlit authentication helpers."""
from __future__ import annotations

import os

import requests
import streamlit as st

try:
    from frontend.ui import apply_branding
except ModuleNotFoundError:
    from ui import apply_branding

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def is_logged_in() -> bool:
    return bool(st.session_state.get("access_token"))


def auth_headers() -> dict[str, str]:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def logout() -> None:
    for key in ("access_token", "token_type", "admin_username"):
        st.session_state.pop(key, None)


def show_login() -> bool:
    """Render the administrator login form and return login state."""
    if is_logged_in():
        return True

    apply_branding()
    st.html("""<style>
    .stApp{background:radial-gradient(circle at 90% 15%,#4c46f8 0,transparent 25%),radial-gradient(circle at 78% 83%,#6d2df4 0,transparent 22%),linear-gradient(135deg,#06132e 0%,#081b45 53%,#101b5b 100%)!important;color:#fff}
    [data-testid="stHeader"],[data-testid="stMain"]{background:transparent}.block-container{padding-top:3.5rem!important;max-width:1240px!important}
    .hw-login-brand,.hw-login-brand *{color:#fff}.hw-login-brand{font-size:1.45rem;font-weight:800}.hw-login-badge{display:inline-block;margin-top:1rem;padding:.28rem .65rem;border-radius:999px;background:rgba(82,89,210,.35);color:#e9e7ff;font-size:.8rem;font-weight:700}.hw-login-title{font-size:2.45rem;line-height:1.02;font-weight:850;letter-spacing:-.045em;color:#fff;margin:1.2rem 0 .9rem}.hw-login-title span{color:#b55cff}.hw-login-description{font-size:1.02rem;line-height:1.45;max-width:28rem;color:#f0f3ff}.hw-login-feature{display:flex;gap:.75rem;align-items:center;padding:.45rem 0;color:#fff;font-weight:700}.hw-login-feature small{display:block;color:#bdc8e6;font-weight:400;margin-top:.08rem}.hw-feature-icon{display:inline-grid;place-items:center;width:2.5rem;height:2.5rem;border-radius:.65rem;background:linear-gradient(135deg,#8242ff,#3e67ff);font-size:1.2rem}
    [data-testid="stForm"]{background:#fff!important;border:0!important;border-radius:18px!important;padding:1.9rem 2rem!important;box-shadow:0 18px 50px rgba(0,0,0,.28)!important}[data-testid="stForm"] *{color:#101b33!important}[data-testid="stForm"] h2{font-size:1.42rem!important;margin-top:0!important;margin-bottom:.25rem!important}[data-testid="stForm"] [data-testid="stCaptionContainer"] p{color:#536789!important}[data-testid="stForm"] label{font-weight:650!important}[data-testid="stForm"] [data-testid="stTextInput"] [data-baseweb="input"]{min-height:3.05rem!important;border:2px solid #a99af8!important;border-radius:9px!important;background:#fff!important;box-shadow:none!important}[data-testid="stForm"] [data-testid="stTextInput"] [data-baseweb="input"]:focus-within{border-color:#643cff!important;box-shadow:0 0 0 3px rgba(100,60,255,.16)!important}[data-testid="stForm"] input{color:#101b33!important}[data-testid="stForm"] button[kind="primary"]{color:#fff!important;min-height:2.75rem}
    </style>""")
    st.space("small")
    brand, form_col = st.columns([.9, 1.1], gap="large", vertical_alignment="center")
    with brand:
        st.markdown("<div class='hw-login-brand'>👥 HireWise</div>", unsafe_allow_html=True)
        st.markdown("<div class='hw-login-badge'>AI-Powered Recruitment</div>", unsafe_allow_html=True)
        st.markdown("<div class='hw-login-title'>Fairer<br><span>Recruitment</span><br>with AI Agents</div>", unsafe_allow_html=True)
        st.markdown("<div class='hw-login-description'>Automate candidate analysis, reduce bias, and make data-driven hiring decisions.</div>", unsafe_allow_html=True)
        st.space("small")
        for icon, title, detail in (
            ("🧠", "AI-powered candidate analysis", "Leverage AI agents to match the best talent."),
            ("♢", "Fair and transparent evaluation", "Reduce bias with explainable AI."),
            ("♙", "Human-in-the-loop decisions", "Keep humans in control of final hiring decisions."),
        ):
            st.markdown(f"<div class='hw-login-feature'><span class='hw-feature-icon'>{icon}</span><span>{title}<small>{detail}</small></span></div>", unsafe_allow_html=True)
    with form_col:
        with st.form("admin_login_form"):
            st.header("Administrator Login")
            st.caption("Sign in to access the HireWise recruitment system.")
            st.space("small")
            username = st.text_input("Administrator username", placeholder="Enter your username")
            password = st.text_input("Administrator password", type="password", placeholder="Enter your password")
            st.space("small")
            submitted = st.form_submit_button("🔒  Sign in", type="primary", width="stretch")

    if submitted:
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/auth/login",
                data={"username": username, "password": password},
                timeout=15,
            )
            if response.ok:
                payload = response.json()
                st.session_state["access_token"] = payload["access_token"]
                st.session_state["token_type"] = payload.get("token_type", "bearer")
                st.session_state["admin_username"] = username
                st.rerun()
            else:
                detail = response.json().get("detail", "Login failed.")
                st.error(detail)
        except requests.RequestException:
            st.error("Backend is not running. Start FastAPI before signing in.")
    return False


def require_login() -> None:
    """Stop a multipage screen until an administrator is authenticated."""
    if not show_login():
        st.stop()
    show_logout()


def show_logout() -> None:
    if is_logged_in() and st.sidebar.button("Log out"):
        logout()
        st.rerun()
