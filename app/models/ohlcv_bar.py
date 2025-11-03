"""OHLCVBar model - Recent daily OHLCV bars (last 2 years only)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import CheckConstraint, UniqueConstraint, Index
from .mixins import UUIDMixin


class OHLCVBar(SQLModel, UUIDMixin, table=True):
    """Recent daily OHLCV bars (last 2 years only)."""

    __tablename__ = "ohlcv_bar_pg"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    ts: date = Field(nullable=False, index=True)  # Market close date (UTC)
    open: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    high: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    low: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    close: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    volume: int = Field(nullable=False)
    adj_close: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=4)
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Relationships
    instrument: Optional["Instrument"] = Relationship()  # type: ignore
    data_source: Optional["DataSource"] = Relationship()  # type: ignore

    __table_args__ = (
        # OHLCV validation constraints
        CheckConstraint("high >= low", name="check_ohlcv_high_low"),
        CheckConstraint("high >= open AND high >= close", name="check_ohlcv_high_bounds"),
        CheckConstraint("low <= open AND low <= close", name="check_ohlcv_low_bounds"),
        CheckConstraint("volume >= 0", name="check_volume_positive"),
        # Unique constraint to prevent duplicate bars
        UniqueConstraint("instrument_id", "ts", "data_source_id", name="uq_ohlcv_instrument_ts_source"),
        # Composite index for time-series queries (most recent first)
        Index("ix_ohlcv_instrument_ts_desc", "instrument_id", "ts", postgresql_ops={"ts": "DESC"}),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "ts": "2025-11-02",
                "open": 185.50,
                "high": 187.25,
                "low": 184.80,
                "close": 186.90,
                "volume": 52431000,
                "adj_close": 186.90,
            }
        }


# Import at the bottom to avoid circular imports
from .instrument import Instrument  # noqa: E402
from .data_source import DataSource  # noqa: E402
