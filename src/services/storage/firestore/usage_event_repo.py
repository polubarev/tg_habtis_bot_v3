from __future__ import annotations

from datetime import datetime, timezone

from src.config.settings import get_settings
from src.core.logging import get_logger
from src.models.usage_event import UsageEvent
from src.services.storage.firestore.client import FirestoreClient

logger = get_logger(__name__)


class UsageEventRepository:
    """Firestore-backed usage-event repository with in-memory fallback."""

    def __init__(self, client: FirestoreClient | None = None):
        self.client = client
        settings = get_settings()
        self.collection_name = settings.firestore_collection_usage_events
        self._store: list[UsageEvent] = []

    async def create(self, event: UsageEvent) -> bool:
        if self.client and self.client.is_ready:
            try:
                self.client.collection(self.collection_name).document().set(
                    event.model_dump(mode="json")
                )
                self._store.append(event)
                return True
            except Exception as exc:
                logger.warning(
                    "Firestore unavailable for usage events; falling back to memory",
                    error=str(exc),
                )
                self.client = None
        self._store.append(event)
        return False

    async def list_between(self, start: datetime, end: datetime) -> list[UsageEvent]:
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        if self.client and self.client.is_ready:
            try:
                events = [
                    UsageEvent(**doc.to_dict())
                    for doc in self.client.collection(self.collection_name).stream()
                ]
                return [
                    event for event in events if start_utc <= _as_utc(event.occurred_at) < end_utc
                ]
            except Exception as exc:
                logger.warning(
                    "Firestore unavailable for usage events; falling back to memory",
                    error=str(exc),
                )
                self.client = None
        return [
            event for event in self._store if start_utc <= _as_utc(event.occurred_at) < end_utc
        ]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
