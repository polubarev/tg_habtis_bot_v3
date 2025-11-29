from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from src.config.settings import Settings, get_settings
from src.services.storage.firestore.user_repo import UserRepository
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.llm.client import LLMClient
from src.services.transcription.whisper import WhisperClient
from src.services.storage.sheets.client import SheetsClient


async def get_user_repo() -> UserRepository:
    """Dependency for user repository."""

    return UserRepository()

async def get_session_repo() -> SessionRepository:
    """Dependency for session repository."""

    return SessionRepository()


async def get_llm_client() -> LLMClient:
    """Dependency for LLM client."""

    return LLMClient()


async def get_whisper_client() -> WhisperClient:
    """Dependency for Whisper client."""

    return WhisperClient()


async def get_sheets_client() -> SheetsClient:
    """Dependency for Google Sheets client."""

    return SheetsClient()


async def verify_telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> bool:
    """Verify the webhook request is from Telegram."""

    settings = get_settings()
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid secret token")
    return True


UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
SessionRepoDep = Annotated[SessionRepository, Depends(get_session_repo)]
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
WhisperClientDep = Annotated[WhisperClient, Depends(get_whisper_client)]
SheetsClientDep = Annotated[SheetsClient, Depends(get_sheets_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
