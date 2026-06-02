from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional

from telegram import Message, Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.config.settings import Settings, get_settings
from src.models.user import UserProfile
from src.models.usage_event import MetadataValue, UsageEvent
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


def get_session_expired_message(lang: str) -> str:
    messages = MESSAGES_RU if lang == "ru" else MESSAGES_EN
    return messages["session_expired"]


def _get_deps(context: ContextTypes.DEFAULT_TYPE) -> DependencyProvider | None:
    return context.application.bot_data.get("deps")


def get_settings_from_context(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    deps = _get_deps(context)
    if deps and hasattr(deps, "settings"):
        return deps.settings
    return get_settings()


def is_admin_user(user_id: int | None, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id is None:
        return False
    return user_id in get_settings_from_context(context).get_admin_telegram_ids()


def get_session_repo(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.session_repo() if deps else None


def get_user_repo(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.user_repo() if deps else None


def get_feedback_repo(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.feedback_repo() if deps else None


def get_usage_event_repo(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.usage_event_repo() if deps and hasattr(deps, "usage_event_repo") else None


def get_sheets_client(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.sheets_client() if deps else None


def get_llm_client(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.llm_client() if deps else None


def get_whisper_client(context: ContextTypes.DEFAULT_TYPE):
    deps = _get_deps(context)
    return deps.whisper_client() if deps else None


async def increment_usage_stat(profile: Optional[UserProfile], user_repo, field: str) -> None:
    if profile is None or user_repo is None:
        return
    stats = profile.usage_stats
    if not hasattr(stats, field):
        return
    current = getattr(stats, field, 0) or 0
    setattr(stats, field, current + 1)
    profile.usage_stats = stats
    profile.updated_at = datetime.utcnow()
    await user_repo.update(profile)


async def record_usage_event(
    context: ContextTypes.DEFAULT_TYPE,
    event_name: str,
    *,
    user_id: int | None = None,
    feature: str | None = None,
    metadata: dict[str, MetadataValue] | None = None,
) -> None:
    repo = get_usage_event_repo(context)
    if repo is None:
        return
    await repo.create(
        UsageEvent.create(
            event_name,
            user_id=user_id,
            feature=feature,
            metadata=metadata,
        )
    )


async def safe_delete_message(message: Message | None) -> None:
    if message is None:
        return
    try:
        await message.delete()
    except Exception:
        return
