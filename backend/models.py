"""SQLModel ORM tables for HireWise."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class JobVacancy(SQLModel, table=True):
    """Persisted vacancy used by Agent 2 requirement extraction."""

    job_id: str = Field(primary_key=True, max_length=100)
    job_title: str = Field(max_length=200)
    job_description: str = Field(max_length=100_000)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )