"""Instrument model - Universe of tradable symbols (S&P 500 + NASDAQ 100)."""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class Instrument(SQLModel, UUIDMixin, table=True):
    """Universe of tradable symbols (S&P 500 + NASDAQ 100)."""

    __tablename__ = "instrument"

    symbol: str = Field(unique=True, nullable=False, index=True)
    name: Optional[str] = Field(default=None)
    asset_class: str = Field(nullable=False)  # equity, option, index
    exchange: Optional[str] = Field(default=None)
    mic: Optional[str] = Field(default=None)  # Market Identifier Code
    currency: str = Field(default="USD")
    sector: Optional[str] = Field(default=None, index=True)  # GICS sector
    industry: Optional[str] = Field(default=None)
    market_cap: Optional[str] = Field(default=None)  # large, mid, small
    active: bool = Field(default=True)
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_class": "equity",
                "exchange": "NASDAQ",
                "mic": "XNAS",
                "sector": "Technology",
                "market_cap": "large",
                "active": True,
            }
        }
