
from datetime import date, datetime, timedelta, timezone


def parse_relative_date(label: str) -> date:
    """Convert simple labels like 'today'/'yesterday' into a date."""

    now = datetime.now(timezone.utc).date()
    normalized = label.lower()
    if normalized in {"today", "сегодня"}:
        return now
    if normalized in {"yesterday", "вчера"}:
        return now - timedelta(days=1)
    return date.fromisoformat(label)
