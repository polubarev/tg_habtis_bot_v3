
from src.models.entry import ReflectionEntry


def append_reflection_entry(client, sheet_id: str, entry: ReflectionEntry) -> None:
    if client is None:
        raise RuntimeError("Sheets client is not configured")
    sheet = client.open_by_key(sheet_id).worksheet("Reflections")
    row = [entry.date.isoformat()] + [f"{k}:{v}" for k, v in entry.answers.items()]
    sheet.append_row(row)
