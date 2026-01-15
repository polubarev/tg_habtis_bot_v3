from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from src.services.reminders import compute_due_date, pick_next_run_from_times, pick_next_run_smart_nudges


def test_compute_due_date_before_rollover_is_yesterday():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 2, 11, 0, tzinfo=tz)
    assert compute_due_date(now, time(hour=12, minute=0)) == date(2024, 1, 1)


def test_compute_due_date_after_rollover_is_today():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 2, 12, 0, tzinfo=tz)
    assert compute_due_date(now, time(hour=12, minute=0)) == date(2024, 1, 2)


def test_pick_next_run_from_times_same_day():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 2, 13, 0, tzinfo=tz)
    next_run = pick_next_run_from_times(
        [time(hour=9), time(hour=14), time(hour=20)],
        tz,
        now=now,
    )
    assert next_run == datetime(2024, 1, 2, 14, 0, tzinfo=tz)


def test_pick_next_run_from_times_next_day():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 2, 21, 0, tzinfo=tz)
    next_run = pick_next_run_from_times(
        [time(hour=9), time(hour=14), time(hour=20)],
        tz,
        now=now,
    )
    assert next_run == datetime(2024, 1, 3, 9, 0, tzinfo=tz)


def test_pick_next_run_smart_nudges_skips_until_after_rollover_when_yesterday_done():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 2, 10, 0, tzinfo=tz)
    next_run = pick_next_run_smart_nudges(
        times=[time(hour=9), time(hour=11), time(hour=14)],
        tz=tz,
        rollover_time=time(hour=12),
        last_habits_logged_for_date=date(2024, 1, 1),
        now=now,
    )
    assert next_run == datetime(2024, 1, 2, 14, 0, tzinfo=tz)


def test_pick_next_run_smart_nudges_schedules_tomorrow_when_today_done_after_rollover():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 2, 15, 0, tzinfo=tz)
    next_run = pick_next_run_smart_nudges(
        times=[time(hour=9), time(hour=20)],
        tz=tz,
        rollover_time=time(hour=12),
        last_habits_logged_for_date=date(2024, 1, 2),
        now=now,
    )
    assert next_run == datetime(2024, 1, 3, 9, 0, tzinfo=tz)

