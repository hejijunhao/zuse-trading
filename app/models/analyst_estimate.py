"""AnalystEstimate model - Analyst consensus and revisions (EPS + Revenue)."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class AnalystEstimate(SQLModel, UUIDMixin, table=True):
    """Analyst consensus and revisions (EPS + Revenue)."""

    __tablename__ = "analyst_estimate"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    as_of_date: date = Field(nullable=False, index=True)
    target_period: str = Field(nullable=False)  # "FY2025", "Q3 2025"
    estimates: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Optional["Instrument"] = Relationship()  # type: ignore
    data_source: Optional["DataSource"] = Relationship()  # type: ignore


# Import at the bottom to avoid circular imports
from .instrument import Instrument  # noqa: E402
from .data_source import DataSource  # noqa: E402
