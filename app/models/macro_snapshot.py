"""MacroSnapshot model - Daily macroeconomic snapshots."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class MacroSnapshot(SQLModel, UUIDMixin, table=True):
    """Daily macroeconomic snapshots."""

    __tablename__ = "macro_snapshot"

    snapshot_date: date = Field(nullable=False, index=True)
    region: str = Field(nullable=False, index=True)  # "US", "Global", "Asia"
    summary: str = Field(nullable=False)
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    data_source: Optional["DataSource"] = Relationship()  # type: ignore

    __table_args__ = (
        # Unique constraint: one snapshot per region per day
        UniqueConstraint("region", "snapshot_date", name="uq_macro_snapshot_region_date"),
    )


# Import at the bottom to avoid circular imports
from .data_source import DataSource  # noqa: E402
