from __future__ import annotations

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.main import app


def test_admin_login_protects_api_routes() -> None:
    client = TestClient(app)
    settings = get_settings()

    assert client.get("/api/agent1/status").status_code == 401
    assert client.post(
        "/api/auth/login",
        data={"username": settings.admin_username, "password": "wrong"},
    ).status_code == 401

    login = client.post(
        "/api/auth/login",
        data={
            "username": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.get(
        "/api/agent1/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200