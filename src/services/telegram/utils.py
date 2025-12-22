from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.models.user import UserProfile
from src.services.telegram.deps import DependencyProvider


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
    user_repo = get_user_repo(context)
    if not user_repo:
        return None
    return await user_repo.get_by_telegram_id(update.effective_user.id)


def resolve_language(profile: Optional[UserProfile]) -> str:
    if profile and profile.language:
        return profile.language
    return "en"


def _get_deps(context: ContextTypes.DEFAULT_TYPE) -> DependencyProvider | None:
    return context.application.bot_data.get("deps")


def get_session_repo(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.session_repo() if deps else None


def get_user_repo(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.user_repo() if deps else None


def get_sheets_client(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.sheets_client() if deps else None


def get_llm_client(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.llm_client() if deps else None


def get_whisper_client(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.whisper_client() if deps else None
