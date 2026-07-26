
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HabitFieldConfig(BaseModel):
    """Configuration for a single habit field."""

    type: str | list[str]
    description: str
    minimum: Optional[int | float] = None
    maximum: Optional[int | float] = None
    default: Optional[object] = None
    options: Optional[list[str]] = None
    allow_multiple: bool = False
    required: bool = True


class HabitSchema(BaseModel):
    """Complete habit schema for a user."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, HabitFieldConfig] = Field(default_factory=dict)
    version: int = 1
    include_diary: bool = True
