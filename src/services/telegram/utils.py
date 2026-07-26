from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Optional

from telegram import Message, Update
from telegram.constants import MessageLimit, ParseMode
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.config.settings import Settings, get_settings
from src.models.user import UserProfile
from src.models.usage_event import MetadataValue, UsageEvent
from src.services.telegram.deps import DependencyProvider


TELEGRAM_TEXT_CHUNK_SIZE = int(MessageLimit.MAX_TEXT_LENGTH) - 96
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def telegram_text_length(text: str) -> int:
    """Return Telegram's UTF-16 text length."""

    return len(text.encode("utf-16-le")) // 2


def split_telegram_text(
    text: str,
    *,
    max_length: int = TELEGRAM_TEXT_CHUNK_SIZE,
) -> list[str]:
    """Split text into Telegram-safe chunks without dropping content."""

    if max_length <= 0:
        raise ValueError("max_length must be positive")
    if not text:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    last_break_at = -1

    for character in text:
        character_length = 2 if ord(character) > 0xFFFF else 1
        while current and current_length + character_length > max_length:
            if last_break_at >= len(current) // 2:
                split_at = last_break_at + 1
                chunks.append("".join(current[:split_at]))
                current = current[split_at:]
                current_length = telegram_text_length("".join(current))
            else:
                chunks.append("".join(current))
                current = []
                current_length = 0
            last_break_at = max(
                (index for index, char in enumerate(current) if char.isspace()),
                default=-1,
            )
        current.append(character)
        current_length += character_length
        if character.isspace():
            last_break_at = len(current) - 1

    if current:
        chunks.append("".join(current))
    return chunks


def _html_to_plain_text(text: str) -> str:
    """Convert the small Telegram HTML subset used by this project to text."""

    return html.unescape(_HTML_TAG_RE.sub("", text))


async def reply_text_chunked(
    message: Message,
    text: str,
    **kwargs: Any,
) -> list[Message]:
    """Reply in safe-sized chunks, placing reply markup on the final chunk."""

    options = dict(kwargs)
    parse_mode = options.get("parse_mode")
    if telegram_text_length(text) > TELEGRAM_TEXT_CHUNK_SIZE and parse_mode in {
        ParseMode.HTML,
        "HTML",
        "html",
    }:
        text = _html_to_plain_text(text)
        options.pop("parse_mode", None)

    chunks = split_telegram_text(text)
    if not chunks:
        return []

    reply_markup = options.pop("reply_markup", None)
    sent: list[Message] = []
    for index, chunk in enumerate(chunks):
        chunk_options = dict(options)
        if index == len(chunks) - 1 and reply_markup is not None:
            chunk_options["reply_markup"] = reply_markup
        sent.append(await message.reply_text(chunk, **chunk_options))
    return sent


async def reply_confirmation_preview(
    message: Message,
    heading: str,
    preview: str,
    *,
    reply_markup: Any,
) -> list[Message]:
    """Send a full confirmation preview, with controls on the last chunk."""

    return await reply_text_chunked(
        message,
        f"{heading}\n{preview}",
        reply_markup=reply_markup,
    )


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
    profile.updated_at = datetime.now(timezone.utc)
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
