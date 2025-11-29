
from typing import Optional

from src.models.user import UserProfile
from src.services.storage.interfaces import IUserRepository


class UserRepository(IUserRepository):
    """Placeholder Firestore-backed user repository."""

    def __init__(self, client=None):
        self.client = client

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserProfile]:
        return None

    async def create(self, user: UserProfile) -> UserProfile:
        return user

    async def update(self, user: UserProfile) -> UserProfile:
        return user

    async def delete(self, telegram_id: int) -> bool:
        return False
