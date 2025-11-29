
from typing import Optional

from src.models.user import UserProfile


class UserRepository:
    """Placeholder Firestore-backed user repository."""

    def __init__(self, client):
        self.client = client

    def get_by_id(self, user_id: int) -> Optional[UserProfile]:
        # TODO: implement Firestore access
        return None

    def save(self, profile: UserProfile) -> None:
        # TODO: implement Firestore access
        _ = profile
