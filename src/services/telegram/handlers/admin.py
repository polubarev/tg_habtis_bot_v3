from __future__ import annotations

from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from src.config.constants import BUTTONS_EN, BUTTONS_RU, MESSAGES_EN, MESSAGES_RU
from src.core.analytics import log_event
from src.models.feedback import FeedbackEntry
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.keyboards import (
    build_admin_broadcast_confirm_keyboard,
    build_admin_keyboard,
)
from src.services.telegram.utils import (
    get_feedback_repo,
    get_session_repo,
    get_usage_event_repo,
    get_user_repo,
    is_admin_user,
    record_usage_event,
    resolve_language,
    resolve_user_profile,
)


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


async def _admin_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    profile = await resolve_user_profile(update, context)
    return resolve_language(profile)


def _admin_button_key(text: str) -> str | None:
    for key in (
        "admin_stats",
        "admin_today",
        "admin_week",
        "admin_month",
        "admin_last_30",
        "admin_users",
        "admin_feedback",
        "admin_broadcast",
    ):
        if text in (BUTTONS_EN.get(key), BUTTONS_RU.get(key)):
            return key
    return None


async def _ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    if is_admin_user(user_id, context):
        return True
    if update.message:
        lang = await _admin_language(update, context)
        await update.message.reply_text(_messages_for_lang(lang)["admin_denied"])
    elif update.callback_query:
        await update.callback_query.answer("Admin only", show_alert=True)
    return False


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the admin menu to configured admin users."""

    if not update.message or not update.effective_user:
        return
    log_event("command.admin", user_id=update.effective_user.id)
    if not await _ensure_admin(update, context):
        return
    lang = await _admin_language(update, context)
    await update.message.reply_text(
        _messages_for_lang(lang)["admin_menu"],
        reply_markup=build_admin_keyboard(lang),
    )


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle admin menu buttons."""

    if not update.message or not update.effective_user:
        return False
    text = (update.message.text or "").strip()
    key = _admin_button_key(text)
    if key is None:
        return False
    if not await _ensure_admin(update, context):
        return True
    if key == "admin_stats":
        await _send_admin_stats(update, context)
        return True
    if key == "admin_today":
        await _send_period_stats(update, context, "today")
        return True
    if key == "admin_week":
        await _send_period_stats(update, context, "week")
        return True
    if key == "admin_month":
        await _send_period_stats(update, context, "month")
        return True
    if key == "admin_last_30":
        await _send_period_stats(update, context, "last_30")
        return True
    if key == "admin_users":
        await _send_user_stats(update, context)
        return True
    if key == "admin_feedback":
        await _send_recent_feedback(update, context)
        return True
    if key == "admin_broadcast":
        await _start_broadcast(update, context)
        return True
    return False


async def handle_admin_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Capture a broadcast draft while an admin broadcast session is active."""

    if not update.message or not update.effective_user:
        return False
    session_repo = get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.ADMIN_AWAITING_BROADCAST:
        return False
    lang = await _admin_language(update, context)
    msgs = _messages_for_lang(lang)
    if not await _ensure_admin(update, context):
        session.reset()
        if session_repo:
            await session_repo.save(session)
        return True

    text = (update.message.text or "").strip()
    if text.lower() in {"/cancel", "cancel", "отмена"}:
        session.reset()
        if session_repo:
            await session_repo.save(session)
        await update.message.reply_text(
            msgs["admin_broadcast_cancelled"],
            reply_markup=build_admin_keyboard(lang),
        )
        return True
    if not text:
        await update.message.reply_text(msgs["admin_broadcast_empty"])
        return True

    session.temp_data["broadcast_text"] = text
    if session_repo:
        await session_repo.save(session)
    await update.message.reply_text(
        msgs["admin_broadcast_preview"].format(text=text),
        reply_markup=build_admin_broadcast_confirm_keyboard(lang),
    )
    return True


async def handle_admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm or cancel a pending admin broadcast."""

    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    if not is_admin_user(update.effective_user.id, context):
        await query.message.reply_text(MESSAGES_EN["admin_denied"])
        return

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = _messages_for_lang(lang)
    session_repo = get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    data = query.data or ""

    if data.endswith(":cancel"):
        if session:
            session.reset()
            if session_repo:
                await session_repo.save(session)
        await query.message.reply_text(
            msgs["admin_broadcast_cancelled"],
            reply_markup=build_admin_keyboard(lang),
        )
        return

    if session is None or session.state != ConversationState.ADMIN_AWAITING_BROADCAST:
        await query.message.reply_text(msgs["session_expired"], reply_markup=build_admin_keyboard(lang))
        return
    text = str(session.temp_data.get("broadcast_text") or "").strip()
    if not text:
        await query.message.reply_text(msgs["admin_broadcast_empty"])
        return

    sent, failed = await _broadcast_to_users(context, text)
    await record_usage_event(
        context,
        "broadcast.sent",
        user_id=update.effective_user.id,
        feature="broadcast",
        metadata={"sent": sent, "failed": failed},
    )
    session.reset()
    if session_repo:
        await session_repo.save(session)
    await query.message.reply_text(
        msgs["admin_broadcast_done"].format(sent=sent, failed=failed),
        reply_markup=build_admin_keyboard(lang),
    )


async def _send_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _admin_language(update, context)
    msgs = _messages_for_lang(lang)
    user_repo = get_user_repo(context)
    if user_repo is None:
        await update.message.reply_text(msgs["admin_storage_unavailable"], reply_markup=build_admin_keyboard(lang))
        return
    users = await user_repo.list_all()
    totals = _aggregate_usage(users)
    await update.message.reply_text(
        msgs["admin_stats"].format(
            users_total=len(users),
            users_with_sheet=sum(1 for user in users if user.sheet_id),
            **totals,
        ),
        reply_markup=build_admin_keyboard(lang),
    )


async def _send_recent_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _admin_language(update, context)
    msgs = _messages_for_lang(lang)
    feedback_repo = get_feedback_repo(context)
    if feedback_repo is None:
        await update.message.reply_text(msgs["admin_storage_unavailable"], reply_markup=build_admin_keyboard(lang))
        return
    entries = await feedback_repo.list_recent(limit=10)
    if not entries:
        await update.message.reply_text(msgs["admin_no_feedback"], reply_markup=build_admin_keyboard(lang))
        return
    lines = [msgs["admin_feedback_title"]]
    for entry in entries:
        lines.append(_format_feedback(entry))
    await update.message.reply_text("\n\n".join(lines), reply_markup=build_admin_keyboard(lang))


async def _send_period_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    period_key: str,
) -> None:
    lang = await _admin_language(update, context)
    msgs = _messages_for_lang(lang)
    usage_repo = get_usage_event_repo(context)
    user_repo = get_user_repo(context)
    if usage_repo is None or user_repo is None:
        await update.message.reply_text(
            msgs["admin_analytics_unavailable"],
            reply_markup=build_admin_keyboard(lang),
        )
        return

    start, end, label = _period_range(period_key, lang)
    events = await usage_repo.list_between(start, end)
    users = await user_repo.list_all()
    stats = _aggregate_period_stats(events)
    stats["new_users"] = _count_users_created_between(users, start, end)
    stats["users_with_sheet"] = sum(1 for user in users if user.sheet_id)

    await update.message.reply_text(
        msgs["admin_period_stats"].format(period=label, **stats),
        reply_markup=build_admin_keyboard(lang),
    )


async def _send_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _admin_language(update, context)
    msgs = _messages_for_lang(lang)
    user_repo = get_user_repo(context)
    if user_repo is None:
        await update.message.reply_text(
            msgs["admin_storage_unavailable"],
            reply_markup=build_admin_keyboard(lang),
        )
        return
    users = await user_repo.list_all()
    today_start, today_end, _ = _period_range("today", lang)
    week_start, week_end, _ = _period_range("week", lang)
    month_start, month_end, _ = _period_range("month", lang)
    last_30_start, last_30_end, _ = _period_range("last_30", lang)
    await update.message.reply_text(
        msgs["admin_user_stats"].format(
            users_total=len(users),
            users_with_sheet=sum(1 for user in users if user.sheet_id),
            new_today=_count_users_created_between(users, today_start, today_end),
            new_week=_count_users_created_between(users, week_start, week_end),
            new_month=_count_users_created_between(users, month_start, month_end),
            new_last_30=_count_users_created_between(users, last_30_start, last_30_end),
        ),
        reply_markup=build_admin_keyboard(lang),
    )


async def _start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _admin_language(update, context)
    session_repo = get_session_repo(context)
    if session_repo:
        session = await session_repo.get(update.effective_user.id) or SessionData(
            user_id=update.effective_user.id
        )
        session.state = ConversationState.ADMIN_AWAITING_BROADCAST
        session.temp_data = {}
        await session_repo.save(session)
    await update.message.reply_text(_messages_for_lang(lang)["admin_broadcast_prompt"])


async def _broadcast_to_users(context: ContextTypes.DEFAULT_TYPE, text: str) -> tuple[int, int]:
    user_repo = get_user_repo(context)
    if user_repo is None:
        return 0, 0
    users = await user_repo.list_all()
    sent = 0
    failed = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user.telegram_user_id, text=text)
            sent += 1
        except TelegramError:
            failed += 1
        except Exception:
            failed += 1
    return sent, failed


def _aggregate_usage(users: list[UserProfile]) -> dict[str, int]:
    totals = {"habits": 0, "dream": 0, "thought": 0, "reflection": 0}
    for user in users:
        totals["habits"] += user.usage_stats.habits
        totals["dream"] += user.usage_stats.dream
        totals["thought"] += user.usage_stats.thought
        totals["reflection"] += user.usage_stats.reflection
    return totals


def _aggregate_period_stats(events) -> dict[str, int]:
    active_users = {event.user_id for event in events if event.user_id is not None}
    stats = {
        "active_users": len(active_users),
        "new_users": 0,
        "users_with_sheet": 0,
        "feature_total": 0,
        "habits": 0,
        "dream": 0,
        "thought": 0,
        "reflection": 0,
        "voice": 0,
        "feedback": 0,
        "commands": 0,
        "broadcasts": 0,
        "broadcast_sent": 0,
        "broadcast_failed": 0,
    }
    for event in events:
        if event.event_name == "feature.saved":
            stats["feature_total"] += 1
            if event.feature in {"habits", "dream", "thought", "reflection"}:
                stats[event.feature] += 1
        elif event.event_name == "voice.received":
            stats["voice"] += 1
        elif event.event_name == "feedback.submitted":
            stats["feedback"] += 1
        elif event.event_name == "command.used":
            stats["commands"] += 1
        elif event.event_name == "broadcast.sent":
            stats["broadcasts"] += 1
            stats["broadcast_sent"] += int(event.metadata.get("sent", 0))
            stats["broadcast_failed"] += int(event.metadata.get("failed", 0))
    return stats


def _period_range(period_key: str, lang: str) -> tuple[datetime, datetime, str]:
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period_key == "today":
        return today, today + timedelta(days=1), "Сегодня" if lang == "ru" else "Today"
    if period_key == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7), "Эта неделя" if lang == "ru" else "This week"
    if period_key == "month":
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end, "Этот месяц" if lang == "ru" else "This month"
    start = now - timedelta(days=30)
    return start, now, "Последние 30 дней" if lang == "ru" else "Last 30 days"


def _count_users_created_between(users: list[UserProfile], start: datetime, end: datetime) -> int:
    return sum(1 for user in users if start <= _as_utc(user.created_at) < end)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_feedback(entry: FeedbackEntry) -> str:
    username = f"@{entry.telegram_username}" if entry.telegram_username else entry.telegram_first_name
    user_label = username or str(entry.telegram_user_id)
    created_at = _format_datetime(entry.created_at)
    return f"{created_at} | {user_label} ({entry.telegram_user_id})\n{entry.message}"


def _format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")
