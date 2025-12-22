from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.models.user import UserProfile


def resolve_user_timezone(profile: Optional[UserProfile]):
    """Return user's timezone or UTC on failure."""

    if profile and profile.timezone:
        try:
            return ZoneInfo(profile.timezone)
        except Exception:
            pass
    return timezone.utc


async def resolve_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[UserProfile]:
    if not update.effective_user:
        return None
    user_repo = context.application.bot_data.get("user_repo")
    if not user_repo:
        return None
    return await user_repo.get_by_telegram_id(update.effective_user.id)


def resolve_language(profile: Optional[UserProfile]) -> str:
    if profile and profile.language:
        return profile.language
    return "en"
