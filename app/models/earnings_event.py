"""EarningsEvent model - Earnings reports with results."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class EarningsEvent(SQLModel, UUIDMixin, table=True):
    """Earnings reports with results."""

    __tablename__ = "earnings_event"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    scheduled_for: Optional[datetime] = Field(default=None, index=True)
    report_date: Optional[date] = Field(default=None, index=True)
    fiscal_period: str = Field(nullable=False)  # "Q1 2025"
    results: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Optional["Instrument"] = Relationship()  # type: ignore
    data_source: Optional["DataSource"] = Relationship()  # type: ignore


# Import at the bottom to avoid circular imports
from .instrument import Instrument  # noqa: E402
from .data_source import DataSource  # noqa: E402
