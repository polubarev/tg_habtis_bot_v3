
from typing import Iterable


def ensure_columns(sheet, expected: Iterable[str]) -> None:
    """Ensure sheet has required header columns; create if missing."""

    header = sheet.row_values(1)
    if header:
        missing = [col for col in expected if col not in header]
        if missing:
            sheet.insert_row(header + missing, 1)
    else:
        sheet.insert_row(list(expected), 1)
