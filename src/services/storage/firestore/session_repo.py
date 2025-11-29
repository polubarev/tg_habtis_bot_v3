
from typing import Dict, Optional

from src.models.session import SessionData
from src.services.storage.interfaces import ISessionRepository


class SessionRepository(ISessionRepository):
    """In-memory session repository placeholder."""

    def __init__(self, client=None):
        self.client = client
        self._store: Dict[int, SessionData] = {}

    async def get(self, user_id: int) -> Optional[SessionData]:
        return self._store.get(user_id)

    async def save(self, session: SessionData) -> None:
        self._store[session.user_id] = session

    async def delete(self, user_id: int) -> None:
        self._store.pop(user_id, None)
