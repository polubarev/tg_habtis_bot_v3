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
