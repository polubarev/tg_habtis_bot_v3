from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    from google.api_core.exceptions import GoogleAPIError, NotFound
    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2
except Exception:  # pragma: no cover - optional dependency
    GoogleAPIError = None
    NotFound = None
    tasks_v2 = None
    timestamp_pb2 = None

from src.config.settings import Settings
from src.core.logging import get_logger


logger = get_logger(__name__)
_SECRET_HEADER = "X-Reminder-Secret"
_WEBHOOK_SUFFIX = "/telegram/webhook"
_DISPATCH_SUFFIX = "/reminders/dispatch"


class ReminderScheduleError(RuntimeError):
    pass


def parse_time_text(value: str) -> time | None:
    text = value.strip()
    if not text:
        return None
    if ":" not in text:
        return None
    parts = text.split(":", 1)
    if len(parts) != 2:
        return None
    if not parts[0].isdigit() or not parts[1].isdigit():
        return None
    hours = int(parts[0])
    minutes = int(parts[1])
    if hours < 0 or hours > 23:
        return None
    if minutes < 0 or minutes > 59:
        return None
    return time(hour=hours, minute=minutes)


def format_time_value(value: time) -> str:
    return value.strftime("%H:%M")


def compute_next_run(reminder_time: time, tz: ZoneInfo, now: datetime | None = None) -> datetime:
    current = now or datetime.now(tz)
    target = current.replace(
        hour=reminder_time.hour,
        minute=reminder_time.minute,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target = target + timedelta(days=1)
    return target


def build_dispatch_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith(_DISPATCH_SUFFIX):
        return trimmed
    if trimmed.endswith(_WEBHOOK_SUFFIX):
        trimmed = trimmed[: -len(_WEBHOOK_SUFFIX)]
    return f"{trimmed}{_DISPATCH_SUFFIX}"


def delete_reminder_task(settings: Settings, task_name: str | None) -> None:
    if not task_name:
        return
    if tasks_v2 is None:
        logger.warning("google-cloud-tasks not available; cannot delete reminder task")
        return
    try:
        client = tasks_v2.CloudTasksClient()
        client.delete_task(name=task_name)
    except Exception as exc:
        if NotFound and isinstance(exc, NotFound):
            return
        logger.warning("Failed to delete reminder task", error=str(exc))
        return


def schedule_reminder_task(
    settings: Settings,
    user_id: int,
    reminder_time: time,
    timezone_name: str,
    previous_task_name: str | None = None,
) -> str:
    if tasks_v2 is None or timestamp_pb2 is None:
        raise ReminderScheduleError("google-cloud-tasks not available")
    dispatch_base = settings.get_reminders_dispatch_url() or settings.get_telegram_webhook_url()
    if not dispatch_base:
        raise ReminderScheduleError("Dispatch URL not configured")
    if not settings.reminders_dispatch_secret:
        raise ReminderScheduleError("Dispatch secret not configured")
    if not settings.gcp_project_id:
        raise ReminderScheduleError("GCP project id not configured")

    queue_name = settings.reminders_queue_name
    location = settings.gcp_region
    dispatch_url = build_dispatch_url(dispatch_base)

    try:
        tz = ZoneInfo(timezone_name)
    except Exception as exc:
        raise ReminderScheduleError("Invalid timezone") from exc
    next_run = compute_next_run(reminder_time, tz).astimezone(timezone.utc)
    schedule_timestamp = timestamp_pb2.Timestamp()
    schedule_timestamp.FromDatetime(next_run)

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(settings.gcp_project_id, location, queue_name)

    payload = json.dumps({"user_id": user_id}).encode("utf-8")
    task = {
        "schedule_time": schedule_timestamp,
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": dispatch_url,
            "headers": {
                "Content-Type": "application/json",
                _SECRET_HEADER: settings.reminders_dispatch_secret,
            },
            "body": payload,
        },
    }

    try:
        response = client.create_task(parent=parent, task=task)
    except Exception as exc:
        if GoogleAPIError and isinstance(exc, GoogleAPIError):
            logger.warning("Failed to schedule reminder", error=str(exc))
        else:
            logger.warning("Failed to schedule reminder (unexpected)", error=str(exc))
        raise ReminderScheduleError("Failed to schedule reminder") from exc
    if previous_task_name:
        delete_reminder_task(settings, previous_task_name)
    return response.name
