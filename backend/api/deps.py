"""Shared FastAPI dependencies.

TEMPORARY STUB (owner: Member 1). get_actor() must be replaced with the
logged-in user's name from the JWT token, and role checks (Recruiter /
HR Admin / Viewer) added here. Until then everyone is "dev-user".
"""
from __future__ import annotations


from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.security.auth import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, object]:
    """Validate a bearer token and return its admin claims."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator login required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired administrator token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_actor(claims: dict[str, object] = Depends(get_current_admin)) -> str:
    """Return the authenticated administrator for audit entries."""
    return str(claims["sub"])
