from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.models.enums import EntryType, InputType
from src.models.text_entry_collection import (
    TextEntryCollection,
    TextEntryCollectionStatus,
    TextEntryPart,
)
from src.services.storage.firestore.text_entry_collection_repo import (
    TextEntryCollectionRepository,
)


class CollectionAction(str, Enum):
    DONE = "done"
    UNDO = "undo"
    CANCEL = "cancel"


@dataclass(frozen=True)
class CollectionOutcome:
    code: str
    collection: TextEntryCollection


class EntryCollectionManager:
    """Deep module for starting, extending, and transitioning entry collections."""

    def __init__(self, repository: TextEntryCollectionRepository):
        self.repository = repository

    async def start(
        self,
        *,
        user_id: int,
        chat_id: int,
        entry_type: EntryType,
        context: dict[str, Any] | None = None,
    ) -> TextEntryCollection:
        return await self.repository.start(user_id, chat_id, entry_type, context)

    async def add_part(
        self,
        *,
        user_id: int,
        collection_id: str,
        message_id: int,
        text: str,
        input_type: InputType = InputType.TEXT,
    ) -> CollectionOutcome:
        result = await self.repository.append(
            user_id,
            collection_id,
            TextEntryPart(message_id=message_id, text=text, input_type=input_type),
        )
        return CollectionOutcome(result.code, result.collection)

    async def apply_action(
        self,
        *,
        user_id: int,
        collection_id: str,
        action: CollectionAction,
    ) -> CollectionOutcome:
        if action == CollectionAction.DONE:
            result = await self.repository.claim(user_id, collection_id)
        elif action == CollectionAction.UNDO:
            result = await self.repository.undo(user_id, collection_id)
        else:
            collection = await self.repository.cancel(user_id, collection_id)
            return CollectionOutcome("cancelled", collection)
        return CollectionOutcome(result.code, result.collection)

    async def set_status_message(
        self, *, user_id: int, collection_id: str, message_id: int
    ) -> TextEntryCollection:
        return await self.repository.set_status_message(user_id, collection_id, message_id)

    async def get(self, user_id: int) -> TextEntryCollection | None:
        return await self.repository.get(user_id)

    async def mark_status(
        self,
        *,
        user_id: int,
        collection_id: str,
        status: TextEntryCollectionStatus,
    ) -> TextEntryCollection:
        return await self.repository.set_status(user_id, collection_id, status)

    async def discard(self, user_id: int) -> None:
        await self.repository.delete(user_id)
