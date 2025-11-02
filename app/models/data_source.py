"""DataSource model - External data providers (Saxo, Exa, Perplexity, etc.)."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin


class DataSource(SQLModel, UUIDMixin, table=True):
    """External data providers (Saxo, Exa, Perplexity, etc.)."""

    __tablename__ = "data_source"

    name: str = Field(unique=True, nullable=False, index=True)
    type: str = Field(nullable=False)  # api, rss, scraper, manual
    base_url: Optional[str] = Field(default=None)
    status: str = Field(default="active")  # active, disabled, rate_limited
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "saxo",
                "type": "api",
                "base_url": "https://gateway.saxobank.com/sim/openapi",
                "status": "active",
                "meta": {"rate_limit": 100, "timeout": 30},
            }
        }
