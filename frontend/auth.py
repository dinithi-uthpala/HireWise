"""Shared Streamlit authentication helpers."""
from __future__ import annotations

import os

import requests
import streamlit as st

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

    st.title("HireWise Administrator Login")
    st.caption("Sign in to access recruitment data and recruiter actions.")
    with st.form("admin_login_form"):
        username = st.text_input("Administrator username")
        password = st.text_input("Administrator password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

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