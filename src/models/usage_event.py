from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


MetadataValue = str | int | bool


class UsageEvent(BaseModel):
    """Content-free analytics event for in-bot admin statistics."""

    user_id: Optional[int] = None
    event_name: str
    feature: Optional[str] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    day: str = ""
    week: str = ""
    month: str = ""
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        event_name: str,
        *,
        user_id: int | None = None,
        feature: str | None = None,
        occurred_at: datetime | None = None,
        metadata: dict[str, MetadataValue] | None = None,
    ) -> "UsageEvent":
        timestamp = _as_utc(occurred_at or datetime.now(timezone.utc))
        iso_year, iso_week, _ = timestamp.isocalendar()
        return cls(
            user_id=user_id,
            event_name=event_name,
            feature=feature,
            occurred_at=timestamp,
            day=timestamp.date().isoformat(),
            week=f"{iso_year}-W{iso_week:02d}",
            month=f"{timestamp.year:04d}-{timestamp.month:02d}",
            metadata=metadata or {},
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
