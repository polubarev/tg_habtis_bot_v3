
from typing import Optional

from src.models.session import ConversationState


class SessionRepository:
    """Placeholder Firestore-backed session repository."""

    def __init__(self, client):
        self.client = client

    def get(self, user_id: int) -> Optional[ConversationState]:
        # TODO: implement Firestore access
        return None

    def save(self, session: ConversationState) -> None:
        # TODO: implement Firestore access
        _ = session
