
from typing import Optional

from pydantic import BaseModel, Field


class HabitFieldConfig(BaseModel):
    """Configuration for a single habit field."""

    type: str | list[str]
    description: str
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    default: Optional[object] = None
    required: bool = True


class HabitSchema(BaseModel):
    """Complete habit schema for a user."""

    fields: dict[str, HabitFieldConfig] = Field(default_factory=dict)
    version: int = 1

    class Config:
        extra = "forbid"
