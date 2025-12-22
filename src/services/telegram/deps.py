from __future__ import annotations

from typing import TYPE_CHECKING

from src.config.settings import Settings

if TYPE_CHECKING:
    from src.services.llm.client import LLMClient
    from src.services.storage.firestore.client import FirestoreClient
    from src.services.storage.firestore.session_repo import SessionRepository
    from src.services.storage.firestore.user_repo import UserRepository
    from src.services.storage.sheets.client import SheetsClient
    from src.services.transcription.whisper import WhisperClient


class DependencyProvider:
    """Lazy container for external clients and repositories."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._firestore_client: FirestoreClient | None = None
        self._session_repo: SessionRepository | None = None
        self._user_repo: UserRepository | None = None
        self._sheets_client: SheetsClient | None = None
        self._llm_client: LLMClient | None = None
        self._whisper_client: WhisperClient | None = None
        self._llm_initialized = False
        self._whisper_initialized = False

    def firestore_client(self) -> FirestoreClient:
        if self._firestore_client is None:
            from src.services.storage.firestore.client import FirestoreClient

            self._firestore_client = FirestoreClient(
                self._settings.google_credentials_path,
                self._settings.gcp_project_id,
            )
        return self._firestore_client

    def session_repo(self) -> SessionRepository:
        if self._session_repo is None:
            from src.services.storage.firestore.session_repo import SessionRepository

            self._session_repo = SessionRepository(self.firestore_client())
        return self._session_repo

    def user_repo(self) -> UserRepository:
        if self._user_repo is None:
            from src.services.storage.firestore.user_repo import UserRepository

            self._user_repo = UserRepository(self.firestore_client())
        return self._user_repo

    def sheets_client(self) -> SheetsClient:
        if self._sheets_client is None:
            from src.services.storage.sheets.client import SheetsClient

            self._sheets_client = SheetsClient(self._settings.google_credentials_path)
        return self._sheets_client

    def llm_client(self) -> LLMClient | None:
        if not self._llm_initialized:
            self._llm_initialized = True
            try:
                from src.services.llm.client import LLMClient

                self._llm_client = LLMClient()
            except Exception:
                self._llm_client = None
        return self._llm_client

    def whisper_client(self) -> WhisperClient | None:
        if not self._whisper_initialized:
            self._whisper_initialized = True
            try:
                from src.services.transcription.whisper import WhisperClient

                self._whisper_client = WhisperClient()
            except Exception:
                self._whisper_client = None
        return self._whisper_client
