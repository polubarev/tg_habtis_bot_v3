from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from src.config.settings import Settings, get_settings
from src.core.dependencies import verify_telegram_webhook
from src.core.logging import setup_logging
from src.services.telegram.bot import TelegramBotService

app = FastAPI(title="Habits & Diary Bot", version="0.1.0")
setup_logging()


def get_bot_service(settings: Settings = Depends(get_settings)) -> TelegramBotService:
    return TelegramBotService(settings)


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