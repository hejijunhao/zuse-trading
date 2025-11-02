"""FinancialStatement model - Consolidated financial statements (quarterly/annual)."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class FinancialStatement(SQLModel, UUIDMixin, table=True):
    """Consolidated financial statements (quarterly/annual)."""

    __tablename__ = "financial_statement"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    period_end: date = Field(nullable=False, index=True)
    period_type: str = Field(nullable=False)  # Q1, Q2, Q3, Q4, FY
    fiscal_year: int = Field(nullable=False)
    income_statement: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    balance_sheet: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    cash_flow: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Optional["Instrument"] = Relationship()  # type: ignore
    data_source: Optional["DataSource"] = Relationship()  # type: ignore


# Import at the bottom to avoid circular imports
from .instrument import Instrument  # noqa: E402
from .data_source import DataSource  # noqa: E402
