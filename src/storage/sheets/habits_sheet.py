
from typing import Any, Iterable

from src.models.entry import HabitEntry


def append_habit_entry(client, sheet_id: str, field_order: Iterable[str], entry: HabitEntry) -> None:
    """Append a habit entry to the Habits sheet."""

    if client is None:
        raise RuntimeError("Sheets client is not configured")
    sheet = client.open_by_key(sheet_id).worksheet("Habits")
    sheet.append_row(entry.to_sheet_row(list(field_order)))
