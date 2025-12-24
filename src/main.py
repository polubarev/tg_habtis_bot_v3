from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Bot
from telegram.error import TelegramError

from src.config.settings import Settings, get_settings
from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.core.dependencies import UserRepoDep, SettingsDep, verify_reminder_dispatch, verify_telegram_webhook
from src.core.logging import setup_logging
from functools import lru_cache

from src.services.telegram.bot import TelegramBotService
from src.services.telegram.utils import resolve_language
from src.services.reminders import ReminderScheduleError, parse_time_text, schedule_reminder_task

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
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    if not isinstance(user_id, int):
        return JSONResponse({"ok": False, "error": "user_id_missing"}, status_code=400)
    profile = await user_repo.get_by_telegram_id(user_id)
    if not profile or not profile.reminder_enabled or not profile.reminder_time:
        return JSONResponse({"ok": True, "skipped": "disabled"})

    reminder_time = parse_time_text(profile.reminder_time)
    if not reminder_time:
        return JSONResponse({"ok": True, "skipped": "invalid_time"})

    bot_token = settings.get_telegram_bot_token()
    if not bot_token:
        return JSONResponse({"ok": False, "error": "bot_token_missing"}, status_code=500)

    try:
        bot = Bot(token=bot_token)
        lang = resolve_language(profile)
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
