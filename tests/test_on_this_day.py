from datetime import date, datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.on_this_day import (
    OnThisDayPayload,
    _shift_year,
    assemble_payloads,
    compute_on_this_day_dates,
    format_on_this_day_message,
    should_autopush_skip_for_new_user,
)
from src.models.user import UserProfile
from src.config.settings import Settings
from src import main as main_module
from src.services.telegram.handlers import on_this_day as on_this_day_handler
from src.services.telegram.utils import TELEGRAM_TEXT_CHUNK_SIZE, telegram_text_length


def test_shift_year_normal_day():
    assert _shift_year(date(2026, 4, 11), 1) == date(2025, 4, 11)
    assert _shift_year(date(2026, 4, 11), 3) == date(2023, 4, 11)


def test_shift_year_feb_29_to_feb_28_in_non_leap_year():
    # Feb 29, 2024 → Feb 28, 2023 (not a leap year).
    assert _shift_year(date(2024, 2, 29), 1) == date(2023, 2, 28)
    # Feb 29, 2024 → Feb 29, 2020 (also leap year — preserved).
    assert _shift_year(date(2024, 2, 29), 4) == date(2020, 2, 29)


def test_compute_on_this_day_dates_returns_years_back():
    today = date(2026, 4, 11)
    result = compute_on_this_day_dates(today, max_years_back=4)
    assert result == [
        date(2025, 4, 11),
        date(2024, 4, 11),
        date(2023, 4, 11),
        date(2022, 4, 11),
    ]


def test_compute_on_this_day_dates_feb_29_today_maps_to_feb_28_past():
    today = date(2024, 2, 29)
    result = compute_on_this_day_dates(today, max_years_back=3)
    # 2023 and 2022 aren't leap → Feb 28; 2021 also not leap → Feb 28.
    assert result == [date(2023, 2, 28), date(2022, 2, 28), date(2021, 2, 28)]


def test_compute_on_this_day_dates_default_max_is_10():
    today = date(2026, 4, 11)
    result = compute_on_this_day_dates(today)
    assert len(result) == 10
    assert result[0] == date(2025, 4, 11)
    assert result[-1] == date(2016, 4, 11)


def test_should_autopush_skip_for_new_user_true():
    today = date(2026, 4, 11)
    assert should_autopush_skip_for_new_user(today, datetime(2025, 10, 1)) is True


def test_should_autopush_skip_for_new_user_false():
    today = date(2026, 4, 11)
    assert should_autopush_skip_for_new_user(today, datetime(2023, 1, 1)) is False


def test_should_autopush_skip_for_new_user_missing_created_at():
    today = date(2026, 4, 11)
    # Unknown created_at — let sheets decide, don't skip.
    assert should_autopush_skip_for_new_user(today, None) is False


def test_assemble_payloads_groups_by_year_and_drops_empty():
    target_dates = [date(2025, 4, 11), date(2024, 4, 11)]
    habits = [
        {"date": "2025-04-11", "diary": "good day", "sleep": "7"},
        # No habit row for 2024-04-11.
    ]
    dreams = [{"date": "2024-04-11", "record": "flew"}]
    thoughts = []
    reflections = []
    payloads = assemble_payloads(target_dates, habits, dreams, thoughts, reflections)
    assert len(payloads) == 2
    assert payloads[0].year == 2025
    assert payloads[0].habits is not None
    assert payloads[0].habits["diary"] == "good day"
    assert payloads[1].year == 2024
    assert payloads[1].habits is None
    assert payloads[1].dreams == [{"date": "2024-04-11", "record": "flew"}]


def test_assemble_payloads_drops_year_with_no_entries():
    target_dates = [date(2025, 4, 11), date(2024, 4, 11)]
    habits = [{"date": "2025-04-11", "diary": "hi"}]
    payloads = assemble_payloads(target_dates, habits, [], [], [])
    assert len(payloads) == 1
    assert payloads[0].year == 2025


def test_format_on_this_day_message_ru_has_year_blocks():
    today = date(2026, 4, 11)
    payloads = [
        OnThisDayPayload(
            year=2025,
            target_date=date(2025, 4, 11),
            habits={"diary": "хороший день", "sleep": "7"},
            dreams=[],
            thoughts=[],
            reflections=[],
        ),
        OnThisDayPayload(
            year=2023,
            target_date=date(2023, 4, 11),
            habits=None,
            dreams=[{"record": "летал"}],
            thoughts=[],
            reflections=[],
        ),
    ]
    text = format_on_this_day_message(today, payloads, "ru")
    assert "В этот день" in text
    assert "1 год назад" in text
    assert "3 года назад" in text
    assert "хороший день" in text
    assert "летал" in text


def test_format_on_this_day_message_en():
    today = date(2026, 4, 11)
    payloads = [
        OnThisDayPayload(
            year=2024,
            target_date=date(2024, 4, 11),
            habits={"diary": "nice"},
            dreams=[],
            thoughts=[{"record": "idea"}],
            reflections=[],
        ),
    ]
    text = format_on_this_day_message(today, payloads, "en")
    assert "On this day" in text
    assert "2 years ago" in text
    assert "nice" in text
    assert "idea" in text


@pytest.mark.asyncio
async def test_long_on_this_day_diary_is_sent_without_truncation(monkeypatch):
    original_diary = "A detailed day.\n" * 450
    today = date(2026, 9, 22)
    payloads = [OnThisDayPayload(
        year=2025,
        target_date=date(2025, 9, 22),
        habits={"diary": original_diary},
        dreams=[],
        thoughts=[],
        reflections=[],
    )]
    profile = UserProfile(telegram_user_id=1, language="en", sheet_id="sheet")

    async def resolve_profile(_update, _context):
        return profile

    async def collect(_client, _sheet_id, _profile):
        return payloads, today

    class Message:
        def __init__(self):
            self.replies = []

        async def reply_text(self, text, **kwargs):
            self.replies.append((text, kwargs))
            return SimpleNamespace(delete=AsyncMock())

    monkeypatch.setattr(on_this_day_handler, "resolve_user_profile", resolve_profile)
    monkeypatch.setattr(on_this_day_handler, "get_sheets_client", lambda _context: object())
    monkeypatch.setattr(on_this_day_handler, "collect_on_this_day_payloads", collect)
    message = Message()
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=1))

    await on_this_day_handler.on_this_day_command(update, SimpleNamespace())

    chunks = [text for text, _kwargs in message.replies[1:]]
    assert len(chunks) >= 2
    assert all(telegram_text_length(chunk) <= TELEGRAM_TEXT_CHUNK_SIZE for chunk in chunks)
    assert "".join(chunks) == format_on_this_day_message(today, payloads, "en")


@pytest.mark.asyncio
async def test_scheduled_on_this_day_sends_long_diary_in_chunks(monkeypatch):
    original_diary = "Another detailed day.\n" * 450
    today = date(2026, 9, 22)
    payloads = [OnThisDayPayload(
        year=2025,
        target_date=date(2025, 9, 22),
        habits={"diary": original_diary},
        dreams=[],
        thoughts=[],
        reflections=[],
    )]
    profile = UserProfile(
        telegram_user_id=1,
        language="en",
        sheet_id="sheet",
        on_this_day_enabled=True,
        on_this_day_time="09:00",
        created_at=datetime(2020, 1, 1),
    )

    class Repo:
        async def get_by_telegram_id(self, _user_id):
            return profile

        async def update(self, _profile):
            pass

    class Sheets:
        def __init__(self, _credentials):
            pass

        async def get_habit_entries_for_dates(self, *_args):
            return []

        async def get_dream_entries_for_dates(self, *_args):
            return []

        async def get_thought_entries_for_dates(self, *_args):
            return []

        async def get_reflection_entries_for_dates(self, *_args):
            return []

    class Bot:
        sent = []

        def __init__(self, token):
            pass

        async def send_message(self, **kwargs):
            self.sent.append(kwargs)

    async def request_json():
        return {"user_id": 1, "kind": "on_this_day"}

    Bot.sent = []
    monkeypatch.setattr(main_module, "get_dispatch_rate_limiter", lambda: SimpleNamespace(allow=lambda _id: True))
    monkeypatch.setattr(main_module, "should_autopush_skip_for_new_user", lambda *_args: False)
    monkeypatch.setattr(main_module, "SheetsClient", Sheets)
    monkeypatch.setattr(main_module, "assemble_payloads", lambda *_args: payloads)
    monkeypatch.setattr(main_module, "schedule_on_this_day_task", lambda *_args: "next-task")
    monkeypatch.setattr(main_module, "Bot", Bot)
    monkeypatch.setattr(
        main_module,
        "datetime",
        SimpleNamespace(now=lambda zone: datetime(2026, 9, 22, 10, tzinfo=zone)),
    )

    response = await main_module.reminders_dispatch(
        SimpleNamespace(json=request_json),
        Repo(),
        Settings(_env_file=None, telegram_bot_token="fake"),
    )

    assert json.loads(response.body)["sent"] is True
    assert len(Bot.sent) >= 2
    assert all(telegram_text_length(item["text"]) <= TELEGRAM_TEXT_CHUNK_SIZE for item in Bot.sent)
    assert "".join(item["text"] for item in Bot.sent) == format_on_this_day_message(
        today, payloads, "en"
    )
