from datetime import datetime, timedelta, timezone

import pytest

from src.models.session import SessionData
from src.services.storage.firestore.session_repo import SessionRepository


@pytest.mark.asyncio
async def test_session_save_refreshes_configured_expiry():
    repo = SessionRepository()
    repo.session_ttl_minutes = 15
    session = SessionData(
        user_id=123,
        last_activity=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    before_save = datetime.now(timezone.utc)
    await repo.save(session)

    assert session.last_activity >= before_save
    assert session.expires_at is not None
    assert session.expires_at - session.last_activity == timedelta(minutes=15)


class FakeDocument:
    def __init__(self, sink: dict):
        self._sink = sink

    def set(self, data: dict) -> None:
        self._sink.clear()
        self._sink.update(data)


class FakeCollection:
    def __init__(self, sink: dict):
        self._sink = sink

    def document(self, _doc_id: str) -> FakeDocument:
        return FakeDocument(self._sink)


class FakeFirestoreClient:
    is_ready = True

    def __init__(self) -> None:
        self.written: dict = {}

    def collection(self, _name: str) -> FakeCollection:
        return FakeCollection(self.written)


@pytest.mark.asyncio
async def test_session_expires_at_is_written_as_native_timestamp():
    """SEC-4: Firestore TTL policies only reap docs whose TTL field is a timestamp."""

    client = FakeFirestoreClient()
    repo = SessionRepository(client)
    repo.session_ttl_minutes = 60
    session = SessionData(user_id=123)
    session.pending_entry = {"raw_record": "private diary text"}

    await repo.save(session)

    assert isinstance(client.written["expires_at"], datetime), (
        "expires_at must be a datetime, not an ISO string, or the TTL policy "
        f"silently ignores the document (got {type(client.written['expires_at'])})"
    )
    assert client.written["expires_at"].tzinfo is not None


@pytest.mark.asyncio
async def test_expired_in_memory_session_is_removed():
    repo = SessionRepository()
    session = SessionData(
        user_id=123,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    repo._store[session.user_id] = session

    assert await repo.get(session.user_id) is None
    assert session.user_id not in repo._store
