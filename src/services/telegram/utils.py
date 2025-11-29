from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo
from typing import Optional

from src.models.user import UserProfile


def resolve_user_timezone(profile: Optional[UserProfile]):
    """Return user's timezone or UTC on failure."""

    if profile and profile.timezone:
        try:
            return ZoneInfo(profile.timezone)
        except Exception:
            pass
    return timezone.utc
