
import json

from src.models.entry import ReflectionEntry


def append_reflection_entry(client, sheet_id: str, entry: ReflectionEntry) -> None:
    if client is None:
        raise RuntimeError("Sheets client is not configured")
    sheet = client.open_by_key(sheet_id).worksheet("Reflections")
    header = sheet.row_values(1)
    canonical_header = ["timestamp", "reflections"]
    if header != canonical_header:
        sheet.update("1:1", [canonical_header])
    row = [entry.timestamp.isoformat(), json.dumps(entry.answers, ensure_ascii=False)]
    sheet.append_row(row)
