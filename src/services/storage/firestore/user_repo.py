
from typing import Any, Dict, Optional

try:
    from google.cloud.firestore_v1.base_query import FieldFilter as FieldFilterType
except Exception:  # pragma: no cover - optional dependency
    FieldFilterType: Any = None  # type: ignore[no-redef]

from src.models.user import UserProfile
from src.config.settings import get_settings
from src.core.logging import get_logger
from src.services.storage.firestore.client import FirestoreClient
from src.services.storage.interfaces import IUserRepository

logger = get_logger(__name__)


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

    async def find_by_sheet_id(self, sheet_id: str) -> Optional[UserProfile]:
        """Return the profile that already owns this sheet, if any.

        Used to stop one user binding another user's diary sheet (SEC-1).
        Raises on backend failure so callers can fail closed rather than
        silently allowing the bind.
        """

        if not sheet_id:
            return None
        if self.client and self.client.is_ready:
            collection = self.client.collection(self.collection_name)
            if FieldFilterType is not None:
                query = collection.where(filter=FieldFilterType("sheet_id", "==", sheet_id))
            else:  # pragma: no cover - older client fallback
                query = collection.where("sheet_id", "==", sheet_id)
            for doc in query.limit(1).stream():
                return UserProfile(**doc.to_dict())
            return None
        for profile in self._store.values():
            if profile.sheet_id == sheet_id:
                return profile
        return None

    async def list_all(self) -> list[UserProfile]:
        if self.client and self.client.is_ready:
            try:
                profiles: list[UserProfile] = []
                for doc in self.client.collection(self.collection_name).stream():
                    profiles.append(UserProfile(**doc.to_dict()))
                return profiles
            except Exception as exc:
                logger.warning("Firestore unavailable for users; falling back to memory", error=str(exc))
                self.client = None
        return list(self._store.values())

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
