from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Bot
from telegram.error import TelegramError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.settings import Settings, get_settings
from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.core.dependencies import UserRepoDep, SettingsDep, verify_reminder_dispatch, verify_telegram_webhook
from src.core.logging import setup_logging
from functools import lru_cache
from datetime import datetime
from zoneinfo import ZoneInfo

from src.services.telegram.bot import TelegramBotService
from src.services.telegram.utils import resolve_language
from src.services.reminders import (
    ReminderScheduleError,
    compute_due_date,
    parse_time_text,
    schedule_reminder_task,
    schedule_smart_nudges_task,
)

app = FastAPI(title="Habits & Diary Bot", version="0.1.0")
setup_logging()


@lru_cache()
def get_bot_service_cached() -> TelegramBotService:
    """Singleton bot service to preserve session state across requests."""

    return TelegramBotService(get_settings())


def get_bot_service(_: Settings = Depends(get_settings)) -> TelegramBotService:
    return get_bot_service_cached()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    bot_service: TelegramBotService = Depends(get_bot_service),
    _: bool = Depends(verify_telegram_webhook),
) -> JSONResponse:
    payload = await request.json()
    await bot_service.handle_update(payload)
    return JSONResponse({"ok": True})


@app.post("/reminders/dispatch")
async def reminders_dispatch(
    request: Request,
    user_repo: UserRepoDep,
    settings: SettingsDep,
    _: bool = Depends(verify_reminder_dispatch),
) -> JSONResponse:
    payload = await request.json()
    user_id = payload.get("user_id")
    kind = payload.get("kind") or "daily"
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    if not isinstance(user_id, int):
        return JSONResponse({"ok": False, "error": "user_id_missing"}, status_code=400)
    profile = await user_repo.get_by_telegram_id(user_id)
    if not profile:
        return JSONResponse({"ok": True, "skipped": "no_profile"})

    bot_token = settings.get_telegram_bot_token()
    if not bot_token:
        return JSONResponse({"ok": False, "error": "bot_token_missing"}, status_code=500)

    lang = resolve_language(profile)
    now_local = datetime.now(ZoneInfo(profile.timezone))

    if kind == "smart_nudge":
        if not profile.smart_nudges_enabled or not profile.smart_nudges_times:
            return JSONResponse({"ok": True, "skipped": "smart_nudges_disabled"})
        rollover = parse_time_text(profile.smart_nudges_rollover_time) or parse_time_text("12:00")
        due = compute_due_date(now_local, rollover)
        due_iso = due.isoformat()
        if profile.last_habits_logged_for_date == due_iso:
            should_send = False
        else:
            should_send = True

        if should_send:
            is_yesterday = due < now_local.date()
            msgs = MESSAGES_RU if lang == "ru" else MESSAGES_EN
            text = msgs["smart_nudge_missing_yesterday"] if is_yesterday else msgs["smart_nudge_missing_today"]
            markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            msgs["smart_nudge_log_now"],
                            callback_data=f"habits_date:{due_iso}",
                        ),
                        InlineKeyboardButton(
                            msgs["smart_nudge_disable"],
                            callback_data="smart_nudges:disable",
                        ),
                    ]
                ]
            )
            try:
                bot = Bot(token=bot_token)
                await bot.send_message(chat_id=user_id, text=text, reply_markup=markup)
            except TelegramError as exc:
                return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

        try:
            task_name = schedule_smart_nudges_task(
                settings=settings,
                user_id=user_id,
                timezone_name=profile.timezone,
                times=profile.smart_nudges_times,
                rollover_time=profile.smart_nudges_rollover_time,
                last_habits_logged_for_date=profile.last_habits_logged_for_date,
            )
            profile.smart_nudges_task_name = task_name
        except ReminderScheduleError:
            profile.smart_nudges_task_name = None
            await user_repo.update(profile)
            return JSONResponse({"ok": True, "schedule": "failed"})

        await user_repo.update(profile)
        return JSONResponse({"ok": True, "sent": should_send})

    if not profile.reminder_enabled or not profile.reminder_time:
        return JSONResponse({"ok": True, "skipped": "disabled"})

    reminder_time = parse_time_text(profile.reminder_time)
    if not reminder_time:
        return JSONResponse({"ok": True, "skipped": "invalid_time"})

    try:
        bot = Bot(token=bot_token)
        text = MESSAGES_RU["reminder_message"] if lang == "ru" else MESSAGES_EN["reminder_message"]
        await bot.send_message(chat_id=user_id, text=text)
    except TelegramError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    try:
        task_name = schedule_reminder_task(
            settings,
            user_id,
            reminder_time,
            profile.timezone,
        )
        profile.reminder_task_name = task_name
    except ReminderScheduleError:
        profile.reminder_task_name = None
        await user_repo.update(profile)
        return JSONResponse({"ok": True, "schedule": "failed"})

    await user_repo.update(profile)
    return JSONResponse({"ok": True})
