from datetime import date, datetime

from src.services.on_this_day import (
    OnThisDayPayload,
    _shift_year,
    assemble_payloads,
    compute_on_this_day_dates,
    format_on_this_day_message,
    should_autopush_skip_for_new_user,
)


def test_shift_year_normal_day():
    assert _shift_year(date(2026, 4, 11), 1) == date(2025, 4, 11)
    assert _shift_year(date(2026, 4, 11), 3) == date(2023, 4, 11)


def test_shift_year_feb_29_to_feb_28_in_non_leap_year():
    # Feb 29, 2024 → Feb 28, 2023 (not a leap year).
    assert _shift_year(date(2024, 2, 29), 1) == date(2023, 2, 28)
    # Feb 29, 2024 → Feb 29, 2020 (also leap year — preserved).
    assert _shift_year(date(2024, 2, 29), 4) == date(2020, 2, 29)


def test_compute_on_this_day_dates_less_than_one_year_returns_empty():
    today = date(2026, 4, 11)
    # Created 6 months ago — not a full year yet.
    created = datetime(2025, 10, 1)
    assert compute_on_this_day_dates(today, created) == []


def test_compute_on_this_day_dates_includes_multiple_years():
    today = date(2026, 4, 11)
    created = datetime(2022, 1, 1)
    result = compute_on_this_day_dates(today, created)
    # Expect 4 years: 2025, 2024, 2023, 2022 (all >= created_date).
    assert result == [
        date(2025, 4, 11),
        date(2024, 4, 11),
        date(2023, 4, 11),
        date(2022, 4, 11),
    ]


def test_compute_on_this_day_dates_stops_before_created_at():
    today = date(2026, 4, 11)
    # Created 2023-06-01: 2023-04-11 is BEFORE created → excluded.
    created = datetime(2023, 6, 1)
    result = compute_on_this_day_dates(today, created)
    assert result == [date(2025, 4, 11), date(2024, 4, 11)]


def test_compute_on_this_day_dates_feb_29_today_maps_to_feb_28_past():
    today = date(2024, 2, 29)
    created = datetime(2021, 1, 1)
    result = compute_on_this_day_dates(today, created)
    # 2023 and 2022 and 2021 aren't leap → Feb 28; 2020 (not in result: created too late).
    assert result == [date(2023, 2, 28), date(2022, 2, 28), date(2021, 2, 28)]


def test_should_autopush_skip_for_new_user_true():
    today = date(2026, 4, 11)
    assert should_autopush_skip_for_new_user(today, datetime(2025, 10, 1)) is True


def test_should_autopush_skip_for_new_user_false():
    today = date(2026, 4, 11)
    assert should_autopush_skip_for_new_user(today, datetime(2023, 1, 1)) is False


def test_should_autopush_skip_for_new_user_missing_created_at():
    today = date(2026, 4, 11)
    assert should_autopush_skip_for_new_user(today, None) is True


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
