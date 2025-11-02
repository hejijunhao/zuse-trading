"""CompanySnapshot model - Daily comprehensive company review."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class CompanySnapshot(SQLModel, UUIDMixin, table=True):
    """Daily comprehensive company review."""

    __tablename__ = "company_snapshot"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    snapshot_date: date = Field(nullable=False, index=True)
    summary: str = Field(nullable=False)
    ownership: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    management: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    business_fundamentals: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    competitive_position: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    risks_catalysts: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Optional["Instrument"] = Relationship()  # type: ignore
    data_source: Optional["DataSource"] = Relationship()  # type: ignore


# Import at the bottom to avoid circular imports
from .instrument import Instrument  # noqa: E402
from .data_source import DataSource  # noqa: E402
