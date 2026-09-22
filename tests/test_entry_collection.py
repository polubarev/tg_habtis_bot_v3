import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.config.settings import Settings
from src.models.enums import EntryType, InputType
from src.models.text_entry_collection import TextEntryCollectionStatus
from src.services.entry_collection import CollectionAction, EntryCollectionManager
from src.services.storage.firestore.text_entry_collection_repo import (
    TextEntryCollectionRepository,
)


def _manager(limit: int = 30_000) -> EntryCollectionManager:
    settings = Settings(
        _env_file=None,
        text_entry_max_utf16_units=limit,
        session_ttl_minutes=60,
    )
    return EntryCollectionManager(TextEntryCollectionRepository(settings=settings))


@pytest.mark.asyncio
async def test_parts_are_idempotent_ordered_and_joined():
    manager = _manager()
    collection = await manager.start(
        user_id=1,
        chat_id=2,
        entry_type=EntryType.HABIT,
    )

    await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=20,
        text="second",
    )
    result = await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=10,
        text="first",
    )
    duplicate = await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=10,
        text="ignored",
    )

    assert result.collection.combined_text == "first\n\nsecond"
    assert duplicate.code == "duplicate"
    assert duplicate.collection.combined_text == "first\n\nsecond"


@pytest.mark.asyncio
async def test_mixed_input_and_undo():
    manager = _manager()
    collection = await manager.start(
        user_id=1,
        chat_id=2,
        entry_type=EntryType.DREAM,
    )
    await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=1,
        text="typed",
        input_type=InputType.TEXT,
    )
    added = await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=2,
        text="spoken",
        input_type=InputType.VOICE,
    )
    assert added.collection.combined_input_type == InputType.MIXED

    undone = await manager.apply_action(
        user_id=1,
        collection_id=collection.collection_id,
        action=CollectionAction.UNDO,
    )
    assert undone.collection.combined_text == "typed"
    assert undone.collection.combined_input_type == InputType.TEXT


@pytest.mark.asyncio
async def test_limit_counts_utf16_and_preserves_previous_parts():
    manager = _manager(limit=6)
    collection = await manager.start(
        user_id=1,
        chat_id=2,
        entry_type=EntryType.THOUGHT,
    )
    accepted = await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=1,
        text="😀😀",
    )
    rejected = await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=2,
        text="x",
    )

    assert accepted.collection.total_utf16_units == 4
    assert rejected.code == "too_large"
    assert rejected.collection.combined_text == "😀😀"


@pytest.mark.asyncio
async def test_done_claim_is_atomic_under_concurrency():
    manager = _manager()
    collection = await manager.start(
        user_id=1,
        chat_id=2,
        entry_type=EntryType.REFLECTION,
    )
    await manager.add_part(
        user_id=1,
        collection_id=collection.collection_id,
        message_id=1,
        text="answer",
    )

    results = await asyncio.gather(
        *[
            manager.apply_action(
                user_id=1,
                collection_id=collection.collection_id,
                action=CollectionAction.DONE,
            )
            for _ in range(2)
        ]
    )

    assert sorted(result.code for result in results) == ["claimed", "not_collecting"]
    assert results[0].collection.status == TextEntryCollectionStatus.PROCESSING


@pytest.mark.asyncio
async def test_cancel_marks_collection_cancelled():
    manager = _manager()
    collection = await manager.start(
        user_id=1,
        chat_id=2,
        entry_type=EntryType.HABIT,
    )
    result = await manager.apply_action(
        user_id=1,
        collection_id=collection.collection_id,
        action=CollectionAction.CANCEL,
    )
    assert result.code == "cancelled"
    assert result.collection.status == TextEntryCollectionStatus.CANCELLED


@pytest.mark.asyncio
async def test_expired_collection_is_removed_on_read():
    manager = _manager()
    collection = await manager.start(
        user_id=1,
        chat_id=2,
        entry_type=EntryType.HABIT,
    )
    collection.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    assert await manager.get(1) is None
