from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover - optional dependency
    firestore = None

from src.config.settings import get_settings
from src.models.transcription_batch import (
    TranscriptionBatch,
    TranscriptionBatchItem,
    TranscriptionBatchStatus,
    TranscriptionItemStatus,
)
from src.services.storage.firestore.client import FirestoreClient


@dataclass(frozen=True)
class BatchAppendResult:
    code: str
    batch: TranscriptionBatch


class TranscriptionBatchRepository:
    """Firestore-backed batch store with an in-memory fallback."""

    def __init__(self, client: FirestoreClient | None = None):
        self.client = client
        self.collection_name = get_settings().firestore_collection_transcription_batches
        self._store: dict[int, TranscriptionBatch] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    async def get(self, user_id: int) -> TranscriptionBatch | None:
        if self.client and self.client.is_ready:
            snapshot = await asyncio.to_thread(
                self.client.collection(self.collection_name).document(str(user_id)).get
            )
            if snapshot.exists:
                return TranscriptionBatch(**snapshot.to_dict())
            return None
        return self._store.get(user_id)

    async def _mutate(
        self,
        user_id: int,
        mutation: Callable[[TranscriptionBatch | None], TranscriptionBatch],
    ) -> TranscriptionBatch:
        if self.client and self.client.is_ready and firestore is not None:
            doc_ref = self.client.collection(self.collection_name).document(str(user_id))

            def run() -> TranscriptionBatch:
                transaction = self.client.raw_client.transaction()

                @firestore.transactional
                def apply(transaction):
                    snapshot = doc_ref.get(transaction=transaction)
                    current = TranscriptionBatch(**snapshot.to_dict()) if snapshot.exists else None
                    updated = mutation(current)
                    transaction.set(doc_ref, updated.model_dump(mode="json"))
                    return updated

                return apply(transaction)

            return await asyncio.to_thread(run)

        async with self._lock(user_id):
            updated = mutation(self._store.get(user_id))
            self._store[user_id] = updated
            return updated

    async def create_or_resume(
        self, user_id: int, chat_id: int, ttl_minutes: int
    ) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current and not current.is_collecting_expired and current.status in {
                TranscriptionBatchStatus.COLLECTING,
                TranscriptionBatchStatus.QUEUED,
                TranscriptionBatchStatus.PROCESSING,
            }:
                return current
            now = datetime.utcnow()
            return TranscriptionBatch(
                user_id=user_id,
                chat_id=chat_id,
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(minutes=ttl_minutes),
            )

        return await self._mutate(user_id, mutation)

    async def append_item(
        self,
        user_id: int,
        batch_id: str,
        item: TranscriptionBatchItem,
        *,
        max_items: int,
        max_duration_seconds: int,
        ttl_minutes: int,
    ) -> BatchAppendResult:
        result_code = "accepted"

        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            nonlocal result_code
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            if current.status != TranscriptionBatchStatus.COLLECTING:
                result_code = "not_collecting"
                return current
            if current.is_collecting_expired:
                result_code = "expired"
                return current
            if any(existing.file_unique_id == item.file_unique_id for existing in current.items):
                result_code = "duplicate"
                return current
            if len(current.items) >= max_items:
                result_code = "full"
                return current
            if current.total_duration_seconds + item.duration_seconds > max_duration_seconds:
                result_code = "duration_limit"
                return current
            current.items.append(item)
            current.items.sort(key=lambda value: value.message_id)
            for index, current_item in enumerate(current.items, start=1):
                current_item.index = index
            current.total_duration_seconds += item.duration_seconds
            current.updated_at = datetime.utcnow()
            current.expires_at = current.updated_at + timedelta(minutes=ttl_minutes)
            return current

        batch = await self._mutate(user_id, mutation)
        return BatchAppendResult(result_code, batch)

    async def clear(self, user_id: int, batch_id: str, ttl_minutes: int) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            if current.status == TranscriptionBatchStatus.COLLECTING:
                current.items = []
                current.total_duration_seconds = 0
                current.updated_at = datetime.utcnow()
                current.expires_at = current.updated_at + timedelta(minutes=ttl_minutes)
            return current

        return await self._mutate(user_id, mutation)

    async def cancel(self, user_id: int, batch_id: str) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            if current.status == TranscriptionBatchStatus.COLLECTING:
                current.status = TranscriptionBatchStatus.CANCELLED
                current.items = []
                current.total_duration_seconds = 0
                current.updated_at = datetime.utcnow()
            return current

        return await self._mutate(user_id, mutation)

    async def queue(self, user_id: int, batch_id: str) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            if current.status == TranscriptionBatchStatus.COLLECTING and current.items:
                current.status = TranscriptionBatchStatus.QUEUED
                current.queued_at = datetime.utcnow()
                current.updated_at = current.queued_at
            return current

        return await self._mutate(user_id, mutation)

    async def restore_collecting(self, user_id: int, batch_id: str) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            if current.status == TranscriptionBatchStatus.QUEUED:
                current.status = TranscriptionBatchStatus.COLLECTING
                current.queued_at = None
                current.updated_at = datetime.utcnow()
            return current

        return await self._mutate(user_id, mutation)

    async def claim(self, user_id: int, batch_id: str) -> TranscriptionBatch | None:
        current = await self.get(user_id)
        if current is None or current.batch_id != batch_id:
            return None

        def mutation(batch: TranscriptionBatch | None) -> TranscriptionBatch:
            if batch is None or batch.batch_id != batch_id:
                raise ValueError("batch_not_found")
            if batch.status == TranscriptionBatchStatus.QUEUED:
                batch.status = TranscriptionBatchStatus.PROCESSING
                batch.updated_at = datetime.utcnow()
            return batch

        return await self._mutate(user_id, mutation)

    async def checkpoint_item(
        self,
        user_id: int,
        batch_id: str,
        index: int,
        *,
        transcript: str | None = None,
        error_code: str | None = None,
    ) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            for item in current.items:
                if item.index == index and item.status == TranscriptionItemStatus.PENDING:
                    item.status = (
                        TranscriptionItemStatus.COMPLETED
                        if transcript is not None
                        else TranscriptionItemStatus.FAILED
                    )
                    item.transcript = transcript
                    item.error_code = error_code
                    break
            current.updated_at = datetime.utcnow()
            return current

        return await self._mutate(user_id, mutation)

    async def complete(self, user_id: int, batch_id: str) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            failed = sum(item.status == TranscriptionItemStatus.FAILED for item in current.items)
            completed = sum(item.status == TranscriptionItemStatus.COMPLETED for item in current.items)
            if completed == 0:
                current.status = TranscriptionBatchStatus.FAILED
            elif failed:
                current.status = TranscriptionBatchStatus.COMPLETED_WITH_ERRORS
            else:
                current.status = TranscriptionBatchStatus.COMPLETED
            current.completed_at = datetime.utcnow()
            current.updated_at = current.completed_at
            return current

        return await self._mutate(user_id, mutation)

    async def mark_delivered_and_purge(
        self, user_id: int, batch_id: str
    ) -> TranscriptionBatch:
        def mutation(current: TranscriptionBatch | None) -> TranscriptionBatch:
            if current is None or current.batch_id != batch_id:
                raise ValueError("batch_not_found")
            current.delivered_at = datetime.utcnow()
            current.updated_at = current.delivered_at
            for item in current.items:
                item.file_id = ""
                item.file_unique_id = ""
                item.transcript = None
                item.mime_type = None
            return current

        return await self._mutate(user_id, mutation)
