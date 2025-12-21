
from typing import Dict, List, Optional

import gspread
import json
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

from src.config.constants import (
    DREAMS_SHEET_COLUMNS,
    HABITS_SHEET_COLUMNS,
    THOUGHTS_SHEET_COLUMNS,
)
from src.models.entry import DreamEntry, HabitEntry, ThoughtEntry
from src.services.storage.interfaces import ISheetsClient


class SheetsClient(ISheetsClient):
    """Google Sheets client using a service account."""

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path
        self.client: gspread.Client | None = None
        self.service_email: str | None = None
        if credentials_path:
            creds = Credentials.from_service_account_file(
                credentials_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            self.client = gspread.Client(auth=creds, session=AuthorizedSession(creds))
            self.service_email = creds.service_account_email
        self._cache: Dict[str, gspread.Spreadsheet] = {}

    def _open(self, sheet_id: str):
        if self.client is None:
            raise RuntimeError("Sheets client is not configured")
        if sheet_id not in self._cache:
            self._cache[sheet_id] = self.client.open_by_key(sheet_id)
        return self._cache[sheet_id]

    async def ensure_tabs(self, sheet_id: str) -> None:
        ss = self._open(sheet_id)
        existing = {ws.title: ws for ws in ss.worksheets()}
        for title, header in [
            ("Habits", ["timestamp", "date", "raw_record", "diary"]),  # dynamic fields added on append
            ("Dreams", DREAMS_SHEET_COLUMNS),
            ("Thoughts", THOUGHTS_SHEET_COLUMNS),
            ("Reflections", ["timestamp", "reflections"]),
        ]:
            if title not in existing:
                ws = ss.add_worksheet(title=title, rows=1000, cols=30)
                ws.append_row(header)
            else:
                ws = existing[title]
                current = ws.row_values(1)
                if not current:
                    ws.append_row(header)
                else:
                    # migrate legacy raw_diary -> raw_record if needed
                    migrated = [("raw_record" if col == "raw_diary" else col) for col in current]
                    # migrate reflection date -> timestamp
                    migrated = [("timestamp" if (title == "Reflections" and col == "date") else col) for col in migrated]
                    missing = [col for col in header if col not in migrated]
                    # For reflections, enforce the canonical two columns to avoid drift
                    if title == "Reflections":
                        new_header = ["timestamp", "reflections"]
                    else:
                        new_header = migrated + [m for m in missing if m not in migrated]
                    if new_header != current:
                        ws.update("1:1", [new_header])

    async def append_habit_entry(self, sheet_id: str, field_order: list[str], entry: HabitEntry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Habits")
        base_header = ["timestamp", "date", "raw_record", "diary"]

        # Read and migrate header (handles legacy raw_diary and keeps existing custom columns)
        header = ws.row_values(1)
        if header:
            header = [("raw_record" if col == "raw_diary" else col) for col in header]
        else:
            header = []

        # Preserve existing custom columns to keep alignment of old rows
        # Preserve existing column order from the sheet
        canonical_header = list(header)
        
        # Append missing base fields
        for field in base_header:
            if field not in canonical_header:
                canonical_header.append(field)

        # Append missing schema fields
        for field in field_order:
            if field not in canonical_header:
                canonical_header.append(field)
                
        # Append any extra fields from the entry
        for field in entry.extra_fields.keys():
            if field not in canonical_header:
                canonical_header.append(field)

        if header != canonical_header:
            ws.update("1:1", [canonical_header])

        # Build row aligned to canonical header (so removed fields stay empty, no shifts)
        row = []
        for col in canonical_header:
            if col == "timestamp":
                row.append(entry.created_at.isoformat())
            elif col == "date":
                row.append(entry.date.isoformat())
            elif col == "raw_record":
                row.append(entry.raw_record)
            elif col == "diary":
                row.append(entry.diary or "")
            else:
                row.append(entry.extra_fields.get(col, ""))

        ws.append_row(row, value_input_option="USER_ENTERED")

    async def append_dream_entry(self, sheet_id: str, entry: DreamEntry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Dreams")
        row = [
            entry.timestamp.isoformat(),
            entry.record,
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")

    async def append_thought_entry(self, sheet_id: str, entry: ThoughtEntry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Thoughts")
        row = [
            entry.timestamp.isoformat(),
            entry.record,
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")

    async def append_reflection_entry(self, sheet_id: str, entry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Reflections")
        header = ws.row_values(1)
        canonical_header = ["timestamp", "reflections"]
        if header != canonical_header:
            ws.update("1:1", [canonical_header])
        ws.append_row(
            [
                entry.timestamp.isoformat(),
                json.dumps(entry.answers, ensure_ascii=False),
            ],
            value_input_option="USER_ENTERED",
        )
