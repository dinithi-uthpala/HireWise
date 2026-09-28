"""HireWise FastAPI application entry point.

Agent 1 is exposed through a small REST + JSON contract so the Streamlit
dashboard and later agents use the same validated processing path.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from backend.api.agent1 import router as agent1_router
from backend.api.agent2 import router as agent2_router
from backend.api.agent3 import router as agent3_router
from backend.api.auth import router as auth_router
from backend.api.pipeline import router as pipeline_router
from backend.config import get_settings
from backend.database import create_db_and_tables
from backend.database import engine
from backend.job_catalog import seed_job_catalog
from backend.security.auth import decode_access_token

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
create_db_and_tables()
with Session(engine) as startup_session:
    seed_job_catalog(startup_session)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(agent1_router, prefix="/api")
app.include_router(agent2_router, prefix="/api")
app.include_router(agent3_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.middleware("http")
async def require_admin_for_api(request, call_next):
    """Require an admin JWT for API operations, except login and health checks."""
    open_paths = {"/health", "/api/auth/login", "/docs", "/openapi.json", "/redoc"}
    if request.url.path.startswith("/api/") and request.url.path not in open_paths:
        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Administrator login required."},
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            decode_access_token(authorization.split(" ", 1)[1].strip())
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired administrator token."},
                headers={"WWW-Authenticate": "Bearer"},
            )
    return await call_next(request)

@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return a lightweight readiness response for the dashboard."""
    return {"status": "ok", "service": settings.app_name}