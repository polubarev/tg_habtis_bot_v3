from datetime import date, datetime, timedelta, timezone, tzinfo


def local_today(tz: tzinfo | None = None, now: datetime | None = None) -> date:
    """Return the current calendar date in ``tz`` (UTC when not given)."""

    tz = tz or timezone.utc
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    return current.astimezone(tz).date()


def parse_relative_date(label: str, tz: tzinfo | None = None, now: datetime | None = None) -> date:
    """Convert simple labels like 'today'/'yesterday' into a date in the user's timezone."""

    today = local_today(tz, now)
    normalized = label.strip().lower()
    if normalized in {"today", "сегодня"}:
        return today
    if normalized in {"yesterday", "вчера"}:
        return today - timedelta(days=1)
    return date.fromisoformat(label.strip())
