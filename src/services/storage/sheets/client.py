
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
            ("Habits", HABITS_SHEET_COLUMNS),
            ("Dreams", DREAMS_SHEET_COLUMNS),
            ("Thoughts", THOUGHTS_SHEET_COLUMNS),
            ("Reflections", ["date", "answers_json"]),
        ]:
            if title not in existing:
                ws = ss.add_worksheet(title=title, rows=1000, cols=30)
                ws.append_row(header)
            else:
                ws = existing[title]
                if ws.row_count < 1:
                    ws.append_row(header)

    async def append_habit_entry(self, sheet_id: str, field_order: list[str], entry: HabitEntry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Habits")
        header = ws.row_values(1)
        if not header:
            ws.append_row(["date"] + field_order)
            header = ws.row_values(1)
        missing = [f for f in field_order if f not in header[1:]]
        if missing:
            header.extend(missing)
            ws.update("1:1", [header])
        row = entry.to_sheet_row(field_order)
        ws.append_row(row, value_input_option="USER_ENTERED")

    async def append_dream_entry(self, sheet_id: str, entry: DreamEntry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Dreams")
        row = [
            entry.timestamp.isoformat(),
            entry.date.isoformat(),
            entry.raw_text,
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")

    async def append_thought_entry(self, sheet_id: str, entry: ThoughtEntry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Thoughts")
        row = [
            entry.timestamp.isoformat(),
            entry.raw_text,
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")

    async def append_reflection_entry(self, sheet_id: str, entry) -> None:
        ss = self._open(sheet_id)
        ws = ss.worksheet("Reflections")
        ws.append_row(
            [
                entry.date.isoformat(),
                json.dumps(entry.answers, ensure_ascii=False),
            ],
            value_input_option="USER_ENTERED",
        )
