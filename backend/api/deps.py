"""Shared FastAPI dependencies.

TEMPORARY STUB (owner: Member 1). get_actor() must be replaced with the
logged-in user's name from the JWT token, and role checks (Recruiter /
HR Admin / Viewer) added here. Until then everyone is "dev-user".
"""
from __future__ import annotations


def get_actor() -> str:
    return "dev-user"
