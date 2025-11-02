"""Reusable model mixins for database tables."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)


class TimestampMixin:
    """Mixin for created_at/updated_at timestamps."""

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"onupdate": datetime.utcnow}
    )
