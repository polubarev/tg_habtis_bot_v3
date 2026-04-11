"""Pure helpers for the "On this day" feature.

Computes historical dates (year ago, 2 years ago, ...) and formats them into
a Telegram message grouped by year. Used both by the on-demand command
handler and by the scheduled autopush dispatch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable


def _shift_year(today: date, years_back: int) -> date:
    """Return `today` shifted back `years_back` years.

    February 29 is mapped to February 28 when the target year is not a leap
    year (per product decision: "29ое как 28ое").
    """

    target_year = today.year - years_back
    try:
        return today.replace(year=target_year)
    except ValueError:
        # Feb 29 in a non-leap target year -> fall back to Feb 28.
        return date(target_year, today.month, 28)


def compute_on_this_day_dates(
    today: date,
    created_at: datetime | date | None,
    max_years_back: int = 50,
) -> list[date]:
    """Return the list of past dates to look up for "On this day".

    Starts from `today - 1 year` and goes further back, one year at a time,
    stopping as soon as the candidate date is earlier than `created_at`.
    Returns an empty list if the user is less than a full year old in the bot.
    """

    if created_at is None:
        return []
    if isinstance(created_at, datetime):
        created_date = created_at.date()
    else:
        created_date = created_at

    # Require at least one full year of history.
    one_year_ago = _shift_year(today, 1)
    if one_year_ago < created_date:
        return []

    dates: list[date] = []
    for years_back in range(1, max_years_back + 1):
        candidate = _shift_year(today, years_back)
        if candidate < created_date:
            break
        dates.append(candidate)
    return dates


@dataclass
class OnThisDayPayload:
    year: int
    target_date: date
    habits: dict[str, Any] | None
    dreams: list[dict[str, Any]]
    thoughts: list[dict[str, Any]]
    reflections: list[dict[str, Any]]

    def is_empty(self) -> bool:
        return (
            self.habits is None
            and not self.dreams
            and not self.thoughts
            and not self.reflections
        )


def _group_by_date(entries: list[dict[str, Any]]) -> dict[date, list[dict[str, Any]]]:
    grouped: dict[date, list[dict[str, Any]]] = {}
    for entry in entries:
        raw = entry.get("date")
        if isinstance(raw, str):
            try:
                d = date.fromisoformat(raw)
            except ValueError:
                continue
        elif isinstance(raw, date):
            d = raw
        else:
            continue
        grouped.setdefault(d, []).append(entry)
    return grouped


def assemble_payloads(
    target_dates: list[date],
    habits_entries: list[dict[str, Any]],
    dreams_entries: list[dict[str, Any]],
    thoughts_entries: list[dict[str, Any]],
    reflection_entries: list[dict[str, Any]],
) -> list[OnThisDayPayload]:
    """Group raw sheet entries into per-date payloads, sorted by year desc."""

    habit_by_date: dict[date, dict[str, Any]] = {}
    for entry in habits_entries:
        raw = entry.get("date")
        if not isinstance(raw, str):
            continue
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            continue
        habit_by_date[d] = entry

    dreams_by_date = _group_by_date(dreams_entries)
    thoughts_by_date = _group_by_date(thoughts_entries)
    reflections_by_date = _group_by_date(reflection_entries)

    payloads: list[OnThisDayPayload] = []
    for target in target_dates:
        habits = habit_by_date.get(target)
        dreams = dreams_by_date.get(target, [])
        thoughts = thoughts_by_date.get(target, [])
        reflections = reflections_by_date.get(target, [])
        payload = OnThisDayPayload(
            year=target.year,
            target_date=target,
            habits=habits,
            dreams=dreams,
            thoughts=thoughts,
            reflections=reflections,
        )
        if not payload.is_empty():
            payloads.append(payload)
    return payloads


def _years_ago_label(today: date, target_year: int, lang: str) -> str:
    diff = today.year - target_year
    if lang == "ru":
        if diff == 1:
            return "1 год назад"
        if 2 <= diff <= 4:
            return f"{diff} года назад"
        return f"{diff} лет назад"
    if diff == 1:
        return "1 year ago"
    return f"{diff} years ago"


def _format_habits_section(
    habits: dict[str, Any],
    lang: str,
) -> list[str]:
    """Format a habits row (diary + custom fields) into display lines."""

    lines: list[str] = []
    diary_text = (habits.get("diary") or "").strip()
    if diary_text:
        label = "Дневник" if lang == "ru" else "Diary"
        lines.append(f"📝 *{label}:* {diary_text}")
    # Remaining habit fields (exclude system columns).
    reserved = {"timestamp", "date", "raw_record", "diary", "field_order"}
    habit_pairs = []
    for key, value in habits.items():
        if key in reserved:
            continue
        if value is None or value == "":
            continue
        habit_pairs.append(f"{key}: {value}")
    if habit_pairs:
        label = "Привычки" if lang == "ru" else "Habits"
        lines.append(f"✅ *{label}:* " + ", ".join(habit_pairs))
    return lines


def _format_reflection_entry(entry: dict[str, Any]) -> list[str]:
    raw = entry.get("reflections")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return [str(raw)] if raw else []
    if not isinstance(raw, dict):
        return [str(raw)] if raw else []
    lines = []
    for question, answer in raw.items():
        if not answer:
            continue
        lines.append(f"• _{question}_: {answer}")
    return lines


def format_on_this_day_message(
    today: date,
    payloads: list[OnThisDayPayload],
    lang: str,
) -> str:
    """Render the on-this-day message grouped into per-year blocks."""

    if lang == "ru":
        title = f"🕰 В этот день — {today.strftime('%d.%m')}"
    else:
        title = f"🕰 On this day — {today.strftime('%d %b')}"

    blocks: list[str] = [f"*{title}*"]
    for payload in payloads:
        header = _years_ago_label(today, payload.year, lang)
        date_str = payload.target_date.strftime("%d.%m.%Y")
        blocks.append(f"\n📅 *{header}* ({date_str})")
        if payload.habits:
            for line in _format_habits_section(payload.habits, lang):
                blocks.append(line)
        for dream in payload.dreams:
            record = (dream.get("record") or "").strip()
            if record:
                label = "Сон" if lang == "ru" else "Dream"
                blocks.append(f"😴 *{label}:* {record}")
        for thought in payload.thoughts:
            record = (thought.get("record") or "").strip()
            if record:
                label = "Мысль" if lang == "ru" else "Thought"
                blocks.append(f"💭 *{label}:* {record}")
        for reflection in payload.reflections:
            reflection_lines = _format_reflection_entry(reflection)
            if reflection_lines:
                label = "Рефлексия" if lang == "ru" else "Reflection"
                blocks.append(f"🤔 *{label}:*")
                blocks.extend(reflection_lines)
    return "\n".join(blocks)


def should_autopush_skip_for_new_user(
    today: date,
    created_at: datetime | date | None,
) -> bool:
    """True if user is less than a full year old — skip autopush silently."""

    if created_at is None:
        return True
    created_date = created_at.date() if isinstance(created_at, datetime) else created_at
    # Allow a 1-day slack for timezones / creation-time rounding.
    return (today - created_date) < timedelta(days=365)
