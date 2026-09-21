from __future__ import annotations

import json

try:
    from google.api_core.exceptions import AlreadyExists, GoogleAPIError
    from google.cloud import tasks_v2
    from google.protobuf import duration_pb2
except Exception:  # pragma: no cover - optional dependency
    AlreadyExists = None
    GoogleAPIError = None
    tasks_v2 = None
    duration_pb2 = None

from src.config.settings import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)
_WEBHOOK_SUFFIX = "/telegram/webhook"
_DISPATCH_SUFFIX = "/transcriptions/dispatch"
_SECRET_HEADER = "X-Transcription-Secret"


class TranscriptionScheduleError(RuntimeError):
    pass


def build_transcription_dispatch_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith(_DISPATCH_SUFFIX):
        return trimmed
    if trimmed.endswith(_WEBHOOK_SUFFIX):
        trimmed = trimmed[: -len(_WEBHOOK_SUFFIX)]
    return f"{trimmed}{_DISPATCH_SUFFIX}"


class TranscriptionTaskScheduler:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def enqueue(self, user_id: int, batch_id: str) -> str:
        if tasks_v2 is None or duration_pb2 is None:
            raise TranscriptionScheduleError("google-cloud-tasks not available")
        base_url = (
            self.settings.get_transcription_dispatch_url()
            or self.settings.get_telegram_webhook_url()
        )
        if not base_url or not self.settings.transcription_dispatch_secret:
            raise TranscriptionScheduleError("transcription dispatch is not configured")
        if not self.settings.gcp_project_id:
            raise TranscriptionScheduleError("GCP project id not configured")

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(
            self.settings.gcp_project_id,
            self.settings.gcp_region,
            self.settings.transcription_queue_name,
        )
        task_name = client.task_path(
            self.settings.gcp_project_id,
            self.settings.gcp_region,
            self.settings.transcription_queue_name,
            f"transcription-{batch_id}",
        )
        deadline = duration_pb2.Duration(seconds=self.settings.transcription_task_deadline_seconds)
        task = {
            "name": task_name,
            "dispatch_deadline": deadline,
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": build_transcription_dispatch_url(base_url),
                "headers": {
                    "Content-Type": "application/json",
                    _SECRET_HEADER: self.settings.transcription_dispatch_secret,
                },
                "body": json.dumps({"user_id": user_id, "batch_id": batch_id}).encode("utf-8"),
            },
        }
        try:
            response = client.create_task(parent=parent, task=task)
            return response.name
        except Exception as exc:
            if AlreadyExists and isinstance(exc, AlreadyExists):
                return task_name
            if GoogleAPIError and isinstance(exc, GoogleAPIError):
                logger.warning("Failed to enqueue transcription batch", error=type(exc).__name__)
            raise TranscriptionScheduleError("failed to enqueue transcription batch") from exc
