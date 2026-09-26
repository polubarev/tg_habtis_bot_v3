from datetime import date, datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from src.models.session import ConversationState, SessionData
from src.services.telegram.handlers import habits as habits_module
from src.services.telegram.handlers.habits import handle_habits_date_callback, handle_habits_text
from src.utils.date_parser import local_today, parse_relative_date
from tests.test_entry_collection_handlers import FakeBot, FakeDeps, FakeMessage, FakeSheets, _update

# 22:30 UTC on Sep 26 is already Sep 27 in Moscow (UTC+3) and still Sep 26 in New York.
LATE_UTC = datetime(2026, 9, 26, 22, 30, tzinfo=timezone.utc)


def test_local_today_uses_given_timezone():
    assert local_today(timezone.utc, LATE_UTC) == date(2026, 9, 26)
    assert local_today(ZoneInfo("Europe/Moscow"), LATE_UTC) == date(2026, 9, 27)
    assert local_today(ZoneInfo("America/New_York"), LATE_UTC) == date(2026, 9, 26)


def test_local_today_defaults_to_utc():
    assert local_today(now=LATE_UTC) == date(2026, 9, 26)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("today", date(2026, 9, 27)),
        ("Сегодня", date(2026, 9, 27)),
        ("yesterday", date(2026, 9, 26)),
        ("вчера", date(2026, 9, 26)),
        ("2026-09-01", date(2026, 9, 1)),
    ],
)
def test_parse_relative_date_in_user_timezone(label, expected):
    assert parse_relative_date(label, ZoneInfo("Europe/Moscow"), LATE_UTC) == expected


def test_custom_short_date_uses_local_year(monkeypatch):
    seen_tz = []

    def fake_local_today(tz=None, now=None):
        seen_tz.append(tz)
        return date(2027, 1, 1)

    monkeypatch.setattr(habits_module, "local_today", fake_local_today)
    moscow = ZoneInfo("Europe/Moscow")
    assert habits_module._parse_custom_date("05.03", moscow) == date(2027, 3, 5)
    assert seen_tz == [moscow]


class NoExistingSheets(FakeSheets):
    async def find_latest_habit_entry(self, _sheet_id, _selected):
        return None


def _context(deps):
    return SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=FakeBot())


@pytest.mark.asyncio
async def test_today_button_resolves_in_profile_timezone(monkeypatch):
    deps = FakeDeps()
    deps._sheets_client = NoExistingSheets()
    deps.user_repo().profile.timezone = "Europe/Moscow"
    real_parse = parse_relative_date
    monkeypatch.setattr(
        habits_module,
        "parse_relative_date",
        lambda label, tz=None: real_parse(label, tz, now=LATE_UTC),
    )
    started = []

    async def fake_start(_update, _context, _entry_type, *, flow_context, intro):
        started.append(flow_context)

    monkeypatch.setattr(habits_module, "start_entry_collection", fake_start)

    await handle_habits_date_callback(
        _update(FakeMessage("pick"), callback_data="habits_date:today"), _context(deps)
    )

    assert started == [{"selected_date": "2026-09-27"}]


@pytest.mark.asyncio
async def test_missing_selected_date_falls_back_to_local_today(monkeypatch):
    deps = FakeDeps()
    deps.user_repo().profile.timezone = "Europe/Moscow"
    seen_tz = []

    def fake_local_today(tz=None, now=None):
        seen_tz.append(tz)
        return date(2026, 9, 27)

    monkeypatch.setattr(habits_module, "local_today", fake_local_today)
    await deps.session_repo().save(
        SessionData(user_id=1, state=ConversationState.HABITS_AWAITING_CONTENT)
    )

    await handle_habits_text(_update(FakeMessage("walked")), _context(deps), "walked")

    session = await deps.session_repo().get(1)
    assert session is not None and session.pending_entry is not None
    assert session.pending_entry["date"] == "2026-09-27"
    assert seen_tz == [ZoneInfo("Europe/Moscow")]
    assert datetime.fromisoformat(session.pending_entry["timestamp"]).utcoffset().total_seconds() == 3 * 3600
