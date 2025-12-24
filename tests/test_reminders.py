from datetime import datetime, time
from zoneinfo import ZoneInfo

from src.services.reminders import compute_next_run, parse_time_text


def test_parse_time_text_valid():
    parsed = parse_time_text("9:30")
    assert parsed == time(hour=9, minute=30)


def test_parse_time_text_invalid():
    assert parse_time_text("24:00") is None
    assert parse_time_text("10:60") is None
    assert parse_time_text("abc") is None


def test_compute_next_run_same_day():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 1, 9, 0, tzinfo=tz)
    next_run = compute_next_run(time(hour=10, minute=0), tz, now=now)
    assert next_run == datetime(2024, 1, 1, 10, 0, tzinfo=tz)


def test_compute_next_run_next_day():
    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 1, 10, 0, tzinfo=tz)
    next_run = compute_next_run(time(hour=9, minute=30), tz, now=now)
    assert next_run == datetime(2024, 1, 2, 9, 30, tzinfo=tz)
