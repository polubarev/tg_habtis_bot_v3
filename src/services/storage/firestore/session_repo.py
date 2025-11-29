
from typing import Dict, Optional

from src.models.session import SessionData
from src.services.storage.interfaces import ISessionRepository
from src.services.storage.firestore.client import FirestoreClient
from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class SessionRepository(ISessionRepository):
    """In-memory session repository placeholder."""

    def __init__(self, client: FirestoreClient | None = None):
        self.client = client
        settings = get_settings()
        self.collection_name = settings.firestore_collection_sessions
        self._store: Dict[int, SessionData] = {}

    async def get(self, user_id: int) -> Optional[SessionData]:
        if self.client and self.client.is_ready:
            try:
                doc = self.client.collection(self.collection_name).document(str(user_id)).get()
                if doc.exists:
                    session = SessionData(**doc.to_dict())
                    if session.is_expired():
                        await self.delete(user_id)
                        return None
                    return session
            except Exception as exc:
                # Fall back to in-memory if Firestore is unavailable/disabled
                logger.warning("Firestore unavailable for sessions; falling back to memory", error=str(exc))
                self.client = None
        return self._store.get(user_id)

    async def save(self, session: SessionData) -> None:
        if self.client and self.client.is_ready:
            try:
                data = session.model_dump(mode="json")
                self.client.collection(self.collection_name).document(str(session.user_id)).set(data)
            except Exception as exc:
                logger.warning("Firestore unavailable for sessions; falling back to memory", error=str(exc))
                self.client = None
        self._store[session.user_id] = session

    async def delete(self, user_id: int) -> None:
        if self.client and self.client.is_ready:
            try:
                self.client.collection(self.collection_name).document(str(user_id)).delete()
            except Exception as exc:
                logger.warning("Firestore unavailable for sessions; falling back to memory", error=str(exc))
                self.client = None
        self._store.pop(user_id, None)
