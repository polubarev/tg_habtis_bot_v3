from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from src.services.reminders.scheduler import compute_next_run, parse_time_text
from src.services.reminders.scheduler import schedule_reminders_task_at, ReminderScheduleError
from src.config.settings import Settings


@dataclass(frozen=True)
class SmartNudgeConfig:
    enabled: bool
    times: tuple[time, ...]
    rollover_time: time
    timezone: ZoneInfo


def parse_times_list(value: str) -> list[time]:
    """Parse a comma/space-separated list of HH:MM times into sorted unique times."""

    parts = [part.strip() for part in value.replace(",", " ").split()]
    parsed: list[time] = []
    for part in parts:
        if not part:
            continue
        t = parse_time_text(part)
        if t is None:
            raise ValueError("invalid_time")
        parsed.append(t)
    unique = sorted({t for t in parsed})
    return unique


def compute_due_date(now: datetime, rollover_time: time) -> date:
    """Compute the due date based on local now and rollover time."""

    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    if now.timetz().replace(tzinfo=None) < rollover_time:
        return now.date() - timedelta(days=1)
    return now.date()


def pick_next_run_from_times(
    times: list[time],
    tz: ZoneInfo,
    now: datetime | None = None,
) -> datetime:
    """Pick the next scheduled datetime from a list of daily times."""

    if not times:
        raise ValueError("no_times_configured")
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    else:
        current = current.astimezone(tz)

    # Find earliest still-in-future time today.
    for t in sorted(times):
        candidate = compute_next_run(t, tz, now=current)
        if candidate.date() == current.date():
            return candidate

    # Otherwise first time tomorrow.
    first = sorted(times)[0]
    tomorrow = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return compute_next_run(first, tz, now=tomorrow)


def pick_next_run_smart_nudges(
    *,
    times: list[time],
    tz: ZoneInfo,
    rollover_time: time,
    last_habits_logged_for_date: date | None,
    now: datetime | None = None,
) -> datetime:
    """
    Pick the next nudge run time with a simple optimization:
    - If the current due date is already logged, avoid scheduling again until after the due date can change.
    """

    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    else:
        current = current.astimezone(tz)

    due = compute_due_date(current, rollover_time)
    if last_habits_logged_for_date == due:
        # If we already satisfied yesterday in the morning, wait until rollover so due becomes today.
        if current.time() < rollover_time:
            boundary = current.replace(
                hour=rollover_time.hour,
                minute=rollover_time.minute,
                second=0,
                microsecond=0,
            )
            if boundary <= current:
                boundary = boundary + timedelta(days=1)
            return pick_next_run_from_times(times, tz, now=boundary)

        # After rollover, due is today and is satisfied -> schedule tomorrow's first time.
        tomorrow = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return pick_next_run_from_times(times, tz, now=tomorrow)

    return pick_next_run_from_times(times, tz, now=current)


def schedule_smart_nudges_task(
    *,
    settings: Settings,
    user_id: int,
    timezone_name: str,
    times: list[str],
    rollover_time: str,
    last_habits_logged_for_date: str | None,
    previous_task_name: str | None = None,
) -> str:
    """Schedule the next Smart nudges task for a user."""

    if not times:
        raise ReminderScheduleError("No smart nudge times configured")
    tz = ZoneInfo(timezone_name)
    parsed_times: list[time] = []
    for raw in times:
        t = parse_time_text(raw)
        if t is None:
            raise ReminderScheduleError("Invalid smart nudge time")
        parsed_times.append(t)
    rollover = parse_time_text(rollover_time)
    if rollover is None:
        raise ReminderScheduleError("Invalid rollover time")

    last_logged: date | None = None
    if last_habits_logged_for_date:
        try:
            last_logged = date.fromisoformat(last_habits_logged_for_date)
        except ValueError:
            last_logged = None

    next_run_local = pick_next_run_smart_nudges(
        times=parsed_times,
        tz=tz,
        rollover_time=rollover,
        last_habits_logged_for_date=last_logged,
    )
    payload = {"user_id": user_id, "kind": "smart_nudge"}
    return schedule_reminders_task_at(
        settings=settings,
        schedule_time_utc=next_run_local.astimezone(timezone.utc),
        payload=payload,
        previous_task_name=previous_task_name,
    )
