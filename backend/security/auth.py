"""Admin authentication helpers for the HireWise API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from backend.config import get_settings


def authenticate_admin(username: str, password: str) -> bool:
    """Validate the configured single administrator account."""
    settings = get_settings()
    return username == settings.admin_username and password == settings.admin_password


def create_access_token(username: str) -> str:
    """Create a short-lived JWT for the authenticated administrator."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": username, "role": "admin", "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    """Decode and validate an admin JWT, raising on invalid credentials."""
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("role") != "admin" or not payload.get("sub"):
        raise jwt.InvalidTokenError("Admin token required")
    return payload