"""HireWise FastAPI application entry point.

Agent 1 is exposed through a small REST + JSON contract so the Streamlit
dashboard and later agents use the same validated processing path.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.agent1 import router as agent1_router
from backend.api.agent2 import router as agent2_router
from backend.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(agent1_router, prefix="/api")
app.include_router(agent2_router, prefix="/api")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return a lightweight readiness response for the dashboard."""
    return {"status": "ok", "service": settings.app_name}