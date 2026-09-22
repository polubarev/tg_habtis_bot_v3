from __future__ import annotations

import json
from typing import Any

try:
    from google.api_core.exceptions import AlreadyExists as AlreadyExistsType
    from google.api_core.exceptions import GoogleAPIError as GoogleAPIErrorType
    from google.cloud import tasks_v2 as tasks_v2_module
    from google.protobuf import duration_pb2 as duration_pb2_module  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency
    AlreadyExistsType: Any = None  # type: ignore[no-redef]
    GoogleAPIErrorType: Any = None  # type: ignore[no-redef]
    tasks_v2_module: Any = None  # type: ignore[no-redef]
    duration_pb2_module: Any = None  # type: ignore[no-redef]

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
        if tasks_v2_module is None or duration_pb2_module is None:
            raise TranscriptionScheduleError("google-cloud-tasks not available")
        base_url = (
            self.settings.get_transcription_dispatch_url()
            or self.settings.get_telegram_webhook_url()
        )
        if not base_url or not self.settings.transcription_dispatch_secret:
            raise TranscriptionScheduleError("transcription dispatch is not configured")
        if not self.settings.gcp_project_id:
            raise TranscriptionScheduleError("GCP project id not configured")

        client = tasks_v2_module.CloudTasksClient()
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
        deadline = duration_pb2_module.Duration(
            seconds=self.settings.transcription_task_deadline_seconds
        )
        task = {
            "name": task_name,
            "dispatch_deadline": deadline,
            "http_request": {
                "http_method": tasks_v2_module.HttpMethod.POST,
                "url": build_transcription_dispatch_url(base_url),
                "headers": {
                    "Content-Type": "application/json",
                    _SECRET_HEADER: self.settings.transcription_dispatch_secret,
                },
                "body": json.dumps({"user_id": user_id, "batch_id": batch_id}).encode("utf-8"),
            },
        }
        try:
            response = client.create_task(parent=parent, task=task)  # type: ignore[arg-type]
            return response.name
        except Exception as exc:
            if AlreadyExistsType is not None and isinstance(exc, AlreadyExistsType):
                return task_name
            if GoogleAPIErrorType is not None and isinstance(exc, GoogleAPIErrorType):
                logger.warning("Failed to enqueue transcription batch", error=type(exc).__name__)
            raise TranscriptionScheduleError("failed to enqueue transcription batch") from exc
