"""Database engine + session helpers."""
from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from backend.config import get_settings


_database_url = get_settings().database_url
_connect_args = {"check_same_thread": False} if _database_url.startswith("sqlite") else {}
engine = create_engine(_database_url, connect_args=_connect_args)


def create_db_and_tables() -> None:
    """Create the configured relational tables when the application starts."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Yield one database session for a FastAPI request."""
    with Session(engine) as session:
        yield session