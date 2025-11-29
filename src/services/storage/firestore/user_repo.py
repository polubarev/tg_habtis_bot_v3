
from typing import Dict, Optional

from src.models.user import UserProfile
from src.services.storage.interfaces import IUserRepository
from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)
from src.services.storage.firestore.client import FirestoreClient


class UserRepository(IUserRepository):
    """In-memory user repository placeholder."""

    def __init__(self, client: FirestoreClient | None = None):
        self.client = client
        settings = get_settings()
        self.collection_name = settings.firestore_collection_users
        self._store: Dict[int, UserProfile] = {}

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserProfile]:
        if self.client and self.client.is_ready:
            try:
                doc_ref = self.client.collection(self.collection_name).document(str(telegram_id))
                doc = doc_ref.get()
                if doc.exists:
                    return UserProfile(**doc.to_dict())
            except Exception as exc:
                logger.warning("Firestore unavailable for users; falling back to memory", error=str(exc))
                self.client = None
        return self._store.get(telegram_id)

    async def create(self, user: UserProfile) -> UserProfile:
        if self.client and self.client.is_ready:
            try:
                data = user.model_dump(mode="json")
                self.client.collection(self.collection_name).document(str(user.telegram_user_id)).set(data)
            except Exception as exc:
                logger.warning("Firestore unavailable for users; falling back to memory", error=str(exc))
                self.client = None
        self._store[user.telegram_user_id] = user
        return user

    async def update(self, user: UserProfile) -> UserProfile:
        if self.client and self.client.is_ready:
            try:
                data = user.model_dump(mode="json")
                self.client.collection(self.collection_name).document(str(user.telegram_user_id)).set(data)
            except Exception as exc:
                logger.warning("Firestore unavailable for users; falling back to memory", error=str(exc))
                self.client = None
        self._store[user.telegram_user_id] = user
        return user

    async def delete(self, telegram_id: int) -> bool:
        if self.client and self.client.is_ready:
            try:
                self.client.collection(self.collection_name).document(str(telegram_id)).delete()
            except Exception as exc:
                logger.warning("Firestore unavailable for users; falling back to memory", error=str(exc))
                self.client = None
        return self._store.pop(telegram_id, None) is not None
