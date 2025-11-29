
from src.models.entry import DreamEntry


def append_dream_entry(client, sheet_id: str, entry: DreamEntry) -> None:
    if client is None:
        raise RuntimeError("Sheets client is not configured")
    sheet = client.open_by_key(sheet_id).worksheet("Dreams")
    sheet.append_row([
        entry.timestamp.isoformat(),
        entry.date.isoformat(),
        entry.raw_text,
        entry.mood or "",
        entry.is_lucid if entry.is_lucid is not None else "",
        ",".join(entry.tags),
        entry.summary or "",
    ])
