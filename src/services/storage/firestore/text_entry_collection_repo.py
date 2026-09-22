from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

try:
    from google.cloud import firestore as firestore_module
except Exception:  # pragma: no cover - optional dependency
    firestore_module: Any = None  # type: ignore[no-redef]

from src.config.settings import Settings, get_settings
from src.models.enums import EntryType
from src.models.text_entry_collection import (
    TextEntryCollection,
    TextEntryCollectionStatus,
    TextEntryPart,
    utf16_length,
)
from src.services.storage.firestore.client import FirestoreClient


@dataclass(frozen=True)
class CollectionMutationResult:
    code: str
    collection: TextEntryCollection


class TextEntryCollectionRepository:
    """Transactional collection persistence with an in-memory adapter."""

    def __init__(self, client: FirestoreClient | None = None, settings: Settings | None = None):
        self.client = client
        self.settings = settings or get_settings()
        self.collection_name = self.settings.firestore_collection_text_entry_collections
        self._store: dict[int, TextEntryCollection] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    async def get(self, user_id: int) -> TextEntryCollection | None:
        collection: TextEntryCollection | None
        if self.client and self.client.is_ready:
            snapshot = await asyncio.to_thread(
                self.client.collection(self.collection_name).document(str(user_id)).get
            )
            if not snapshot.exists:
                return None
            collection = TextEntryCollection(**snapshot.to_dict())
        else:
            collection = self._store.get(user_id)
        if collection and collection.is_expired:
            await self.delete(user_id)
            return None
        return collection

    async def _mutate(
        self,
        user_id: int,
        mutation: Callable[[TextEntryCollection | None], TextEntryCollection],
    ) -> TextEntryCollection:
        client = self.client
        if client is not None and client.is_ready and firestore_module is not None:
            doc_ref = client.collection(self.collection_name).document(str(user_id))

            def run() -> TextEntryCollection:
                transaction = client.raw_client.transaction()

                @firestore_module.transactional
                def apply(transaction):
                    snapshot = doc_ref.get(transaction=transaction)
                    current = TextEntryCollection(**snapshot.to_dict()) if snapshot.exists else None
                    updated = mutation(current)
                    data = updated.model_dump(mode="json")
                    if updated.expires_at is not None:
                        data["expires_at"] = updated.expires_at
                    transaction.set(doc_ref, data)
                    return updated

                return apply(transaction)

            return await asyncio.to_thread(run)

        async with self._lock(user_id):
            updated = mutation(self._store.get(user_id))
            self._store[user_id] = updated
            return updated

    async def start(
        self,
        user_id: int,
        chat_id: int,
        entry_type: EntryType,
        context: dict[str, Any] | None = None,
    ) -> TextEntryCollection:
        def mutation(_: TextEntryCollection | None) -> TextEntryCollection:
            collection = TextEntryCollection(
                user_id=user_id,
                chat_id=chat_id,
                entry_type=entry_type,
                context=context or {},
            )
            collection.refresh_expiry(self.settings.session_ttl_minutes)
            return collection

        return await self._mutate(user_id, mutation)

    async def append(
        self,
        user_id: int,
        collection_id: str,
        part: TextEntryPart,
    ) -> CollectionMutationResult:
        code = "accepted"

        def mutation(current: TextEntryCollection | None) -> TextEntryCollection:
            nonlocal code
            if current is None or current.collection_id != collection_id:
                raise ValueError("collection_not_found")
            if current.status != TextEntryCollectionStatus.COLLECTING:
                code = "not_collecting"
                return current
            if any(existing.message_id == part.message_id for existing in current.parts):
                code = "duplicate"
                return current
            separator_units = 2 if current.parts else 0
            proposed = current.total_utf16_units + separator_units + utf16_length(part.text)
            if proposed > self.settings.text_entry_max_utf16_units:
                code = "too_large"
                return current
            current.parts.append(part)
            current.parts.sort(key=lambda value: value.message_id)
            current.total_utf16_units = utf16_length(current.combined_text)
            current.refresh_expiry(self.settings.session_ttl_minutes)
            return current

        collection = await self._mutate(user_id, mutation)
        return CollectionMutationResult(code, collection)

    async def undo(self, user_id: int, collection_id: str) -> CollectionMutationResult:
        code = "removed"

        def mutation(current: TextEntryCollection | None) -> TextEntryCollection:
            nonlocal code
            if current is None or current.collection_id != collection_id:
                raise ValueError("collection_not_found")
            if current.status != TextEntryCollectionStatus.COLLECTING:
                code = "not_collecting"
                return current
            if not current.parts:
                code = "empty"
                return current
            current.parts.sort(key=lambda value: value.message_id)
            current.parts.pop()
            current.total_utf16_units = utf16_length(current.combined_text)
            current.refresh_expiry(self.settings.session_ttl_minutes)
            return current

        collection = await self._mutate(user_id, mutation)
        return CollectionMutationResult(code, collection)

    async def claim(self, user_id: int, collection_id: str) -> CollectionMutationResult:
        code = "claimed"

        def mutation(current: TextEntryCollection | None) -> TextEntryCollection:
            nonlocal code
            if current is None or current.collection_id != collection_id:
                raise ValueError("collection_not_found")
            if current.status not in {
                TextEntryCollectionStatus.COLLECTING,
                TextEntryCollectionStatus.FAILED,
            }:
                code = "not_collecting"
                return current
            if not current.parts:
                code = "empty"
                return current
            current.status = TextEntryCollectionStatus.PROCESSING
            current.refresh_expiry(self.settings.session_ttl_minutes)
            return current

        collection = await self._mutate(user_id, mutation)
        return CollectionMutationResult(code, collection)

    async def set_status(
        self,
        user_id: int,
        collection_id: str,
        status: TextEntryCollectionStatus,
    ) -> TextEntryCollection:
        def mutation(current: TextEntryCollection | None) -> TextEntryCollection:
            if current is None or current.collection_id != collection_id:
                raise ValueError("collection_not_found")
            current.status = status
            current.refresh_expiry(self.settings.session_ttl_minutes)
            return current

        return await self._mutate(user_id, mutation)

    async def set_status_message(
        self, user_id: int, collection_id: str, message_id: int
    ) -> TextEntryCollection:
        def mutation(current: TextEntryCollection | None) -> TextEntryCollection:
            if current is None or current.collection_id != collection_id:
                raise ValueError("collection_not_found")
            current.status_message_id = message_id
            return current

        return await self._mutate(user_id, mutation)

    async def cancel(self, user_id: int, collection_id: str) -> TextEntryCollection:
        return await self.set_status(user_id, collection_id, TextEntryCollectionStatus.CANCELLED)

    async def delete(self, user_id: int) -> None:
        if self.client and self.client.is_ready:
            await asyncio.to_thread(
                self.client.collection(self.collection_name).document(str(user_id)).delete
            )
        self._store.pop(user_id, None)
