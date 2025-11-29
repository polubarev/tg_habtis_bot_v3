
from src.models.entry import ThoughtEntry


def append_thought_entry(client, sheet_id: str, entry: ThoughtEntry) -> None:
    if client is None:
        raise RuntimeError("Sheets client is not configured")
    sheet = client.open_by_key(sheet_id).worksheet("Thoughts")
    sheet.append_row([
        entry.timestamp.isoformat(),
        entry.raw_text,
        ",".join(entry.tags),
    ])
