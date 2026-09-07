"""SQLModel database engine + session helpers.

HireWise uses a *relational* store (default SQLite for the demo,
PostgreSQL via DATABASE_URL in production) for structured application data.
The vector store (ChromaDB) lives in ``backend/ir/vector_store.py``.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from backend.config import get_settings

settings = get_settings()

# SQLModel needs `connect_args` to disable sqlite thread checks.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# echo=True in debug mode is handy during development
engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
)


def create_db_and_tables() -> None:
    """Create all tables defined on SQLModel subclasses (idempotent)."""
    from backend import models  # noqa: F401  (registers table models)

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session