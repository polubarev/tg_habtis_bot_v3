from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.core.exceptions import SheetAccessError
from src.models.entry import DreamEntry, HabitEntry, ReflectionEntry, ThoughtEntry
from src.services.storage.sheets.client import SheetsClient


class FakeWorksheet:
    def __init__(self, title: str, header: list[str]) -> None:
        self.title = title
        self.header = header
        self.appended: list[tuple[list[str], str | None]] = []
        self.updated: list[tuple[str, list[list[str]], str | None]] = []
        self.formatted: list[tuple[str, dict]] = []

    def get(self, *_args, **_kwargs):
        return [["timestamp"]]

    def update(self, range_name, values, value_input_option=None):
        self.updated.append((range_name, values, value_input_option))
        if range_name == "1:1":
            self.header = values[0]

    def row_values(self, index: int):
        return self.header if index == 1 else []

    def append_row(self, row, value_input_option=None):
        self.appended.append((row, value_input_option))

    def format(self, range_name, cell_format):
        self.formatted.append((range_name, cell_format))


class FakeSpreadsheet:
    def __init__(self) -> None:
        self.worksheets_by_title = {
            "Habits": FakeWorksheet("Habits", ["timestamp", "date", "raw_record", "diary"]),
            "Dreams": FakeWorksheet("Dreams", ["timestamp", "record"]),
            "Thoughts": FakeWorksheet("Thoughts", ["timestamp", "record"]),
            "Reflections": FakeWorksheet("Reflections", ["timestamp", "reflections"]),
        }

    def worksheets(self):
        return list(self.worksheets_by_title.values())

    def worksheet(self, title: str):
        return self.worksheets_by_title[title]


def _client_with_fake_spreadsheet():
    client = object.__new__(SheetsClient)
    client._tabs_ensured = set()
    client._cache = {}
    client.credentials_path = None
    client.client = SimpleNamespace()
    client.service_email = None
    spreadsheet = FakeSpreadsheet()
    client._open = lambda _sheet_id: spreadsheet
    return client, spreadsheet


def test_habit_entries_are_written_raw_to_prevent_formula_execution():
    client, spreadsheet = _client_with_fake_spreadsheet()
    entry = HabitEntry(
        date=date(2026, 6, 2),
        raw_record='=IMPORTXML("https://example.com", "//title")',
        diary="+SUM(1,2)",
        created_at=datetime(2026, 6, 2, 12, 0),
    )

    client._append_habit_entry_sync("sheet", [], entry)

    row, value_input_option = spreadsheet.worksheet("Habits").appended[0]
    assert value_input_option == "RAW"
    assert row[1] == 46175
    assert row[2].startswith("=")
    assert row[3].startswith("+")
    assert spreadsheet.worksheet("Habits").formatted == [
        ("B:B", {"numberFormat": {"type": "DATE", "pattern": "dd-mm-yyyy"}})
    ]


def test_habit_entry_sheet_row_uses_numeric_date_for_raw_writes():
    entry = HabitEntry(
        date=date(2026, 6, 2),
        raw_record="record",
        created_at=datetime(2026, 6, 2, 12, 0),
    )

    assert entry.to_sheet_row([])[0] == 46175


def test_other_entry_types_are_written_raw_to_prevent_formula_execution():
    client, spreadsheet = _client_with_fake_spreadsheet()

    client._append_dream_entry_sync(
        "sheet",
        DreamEntry(timestamp=datetime(2026, 6, 2, 12, 0), record="@malicious"),
    )
    client._append_thought_entry_sync(
        "sheet",
        ThoughtEntry(timestamp=datetime(2026, 6, 2, 12, 0), record="-cmd"),
    )
    client._append_reflection_entry_sync(
        "sheet",
        ReflectionEntry(timestamp=datetime(2026, 6, 2, 12, 0), answers={"q": "=1+1"}),
    )

    assert spreadsheet.worksheet("Dreams").appended[0][1] == "RAW"
    assert spreadsheet.worksheet("Thoughts").appended[0][1] == "RAW"
    assert spreadsheet.worksheet("Reflections").appended[0][1] == "RAW"


def test_mapped_sheet_errors_are_not_reclassified_as_write_errors():
    client, _spreadsheet = _client_with_fake_spreadsheet()
    client._open = lambda _sheet_id: (_ for _ in ()).throw(SheetAccessError("denied"))

    with pytest.raises(SheetAccessError):
        client._ensure_tabs_sync("sheet")
