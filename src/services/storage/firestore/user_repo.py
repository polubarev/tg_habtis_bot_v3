
from typing import Dict, Optional

from src.models.user import UserProfile
from src.services.storage.interfaces import IUserRepository


class UserRepository(IUserRepository):
    """In-memory user repository placeholder."""

    def __init__(self, client=None):
        self.client = client
        self._store: Dict[int, UserProfile] = {}

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserProfile]:
        return self._store.get(telegram_id)

    async def create(self, user: UserProfile) -> UserProfile:
        self._store[user.telegram_user_id] = user
        return user

    async def update(self, user: UserProfile) -> UserProfile:
        self._store[user.telegram_user_id] = user
        return user

    async def delete(self, telegram_id: int) -> bool:
        return self._store.pop(telegram_id, None) is not None
