"""SectorSnapshot model - Daily sector-level fundamental snapshots."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class SectorSnapshot(SQLModel, UUIDMixin, table=True):
    """Daily sector-level fundamental snapshots."""

    __tablename__ = "sector_snapshot"

    snapshot_date: date = Field(nullable=False, index=True)
    sector: str = Field(nullable=False, index=True)  # GICS sector
    summary: str = Field(nullable=False)
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    data_source: Optional["DataSource"] = Relationship()  # type: ignore


# Import at the bottom to avoid circular imports
from .data_source import DataSource  # noqa: E402
