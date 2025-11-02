"""Base configurations and common types for database models."""

from datetime import datetime
from typing import TypeAlias
from uuid import UUID
from pydantic import ConfigDict

# Custom type alias for JSONB columns
JSONB: TypeAlias = dict


# Base config for all models
class BaseConfig:
    """Base configuration for all SQLModel database models."""

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )
