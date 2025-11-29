
from datetime import date, datetime, timedelta


def parse_relative_date(label: str) -> date:
    """Convert simple labels like 'today'/'yesterday' into a date."""

    now = datetime.utcnow().date()
    normalized = label.lower()
    if normalized in {"today", "???????"}:
        return now
    if normalized in {"yesterday", "?????"}:
        return now - timedelta(days=1)
    return date.fromisoformat(label)
