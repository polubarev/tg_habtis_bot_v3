
import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import gspread
import json
import requests
import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

from src.config.constants import (
    DREAMS_SHEET_COLUMNS,
    HABITS_SHEET_COLUMNS,
    THOUGHTS_SHEET_COLUMNS,
)
from src.core.exceptions import ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.models.entry import DreamEntry, HabitEntry, ThoughtEntry
from src.services.storage.interfaces import HabitRowLookup, ISheetsClient


class SheetsClient(ISheetsClient):
    """Google Sheets client using a service account."""

    _SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    _WRITE_INPUT_OPTION = "RAW"

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path
        self.client: gspread.Client | None = None
        self.service_email: str | None = None
        self._tabs_ensured: set[str] = set()
        if credentials_path:
            creds = Credentials.from_service_account_file(
                credentials_path, scopes=self._SCOPES
            )
            self.service_email = creds.service_account_email
        else:
            # Use Application Default Credentials (Workload Identity on Cloud Run)
            creds, _ = google.auth.default(scopes=self._SCOPES)
        self.client = gspread.Client(auth=creds, session=AuthorizedSession(creds))
        self._cache: Dict[str, gspread.Spreadsheet] = {}

    @staticmethod
    def _safe_cell_value(values: list[list[str]] | None) -> str:
        if not values or not values[0]:
            return ""
        value = values[0][0]
        return "" if value is None else str(value)

    @staticmethod
    def _parse_sheet_date(value: object) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, (int, float)):
            try:
                base = date(1899, 12, 30)
                return base + timedelta(days=int(value))
            except Exception:
                return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return datetime.fromisoformat(text).date()
            except ValueError:
                pass
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _column_letter(col_index: int) -> str:
        a1 = gspread.utils.rowcol_to_a1(1, col_index)
        return "".join(ch for ch in a1 if ch.isalpha())

    @staticmethod
    def _is_permission_error(exc: Exception) -> bool:
        if isinstance(exc, gspread.exceptions.SpreadsheetNotFound):
            return True
        if isinstance(exc, gspread.exceptions.APIError):
            status = getattr(exc.response, "status_code", None)
            if status in {401, 403}:
                return True
            message = str(exc).lower()
            if (
                "permission" in message
                or "not have permission" in message
                or "protected" in message
                or "read-only" in message
            ):
                return True
        return False

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return True
        if isinstance(exc, requests.exceptions.Timeout):
            return True
        if isinstance(exc, gspread.exceptions.APIError):
            status = getattr(exc.response, "status_code", None)
            if status in {408, 429, 500, 502, 503, 504}:
                return True
        message = str(exc).lower()
        return "timeout" in message or "timed out" in message

    def _raise_mapped_error(self, exc: Exception) -> None:
        if self._is_permission_error(exc):
            raise SheetAccessError("Google Sheet access denied") from exc
        if self._is_timeout_error(exc):
            raise ExternalTimeoutError("Google Sheets request timed out") from exc
        raise SheetWriteError("Google Sheets write failed") from exc

    def _open(self, sheet_id: str):
        if self.client is None:
            raise RuntimeError("Sheets client is not configured")
        if sheet_id not in self._cache:
            try:
                self._cache[sheet_id] = self.client.open_by_key(sheet_id)
            except Exception as exc:
                self._raise_mapped_error(exc)
                raise
        return self._cache[sheet_id]

    def _ensure_write_access(self, worksheet: gspread.Worksheet) -> None:
        try:
            values = worksheet.get("A1", value_render_option="FORMULA")
            value = self._safe_cell_value(values)
            worksheet.update("A1", [[value]], value_input_option=self._WRITE_INPUT_OPTION)
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    def _ensure_tabs_sync(self, sheet_id: str) -> None:
        if sheet_id in self._tabs_ensured:
            return
        try:
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
                    ws.append_row(header, value_input_option=self._WRITE_INPUT_OPTION)
                else:
                    ws = existing[title]
                    current = ws.row_values(1)
                    if not current:
                        ws.append_row(header, value_input_option=self._WRITE_INPUT_OPTION)
                    else:
                        # migrate legacy raw_diary -> raw_record if needed
                        migrated = [("raw_record" if col == "raw_diary" else col) for col in current]
                        # migrate reflection date -> timestamp
                        migrated = [
                            ("timestamp" if (title == "Reflections" and col == "date") else col)
                            for col in migrated
                        ]
                        missing = [col for col in header if col not in migrated]
                        # For reflections, enforce the canonical two columns to avoid drift
                        if title == "Reflections":
                            new_header = ["timestamp", "reflections"]
                        else:
                            new_header = migrated + [m for m in missing if m not in migrated]
                        if new_header != current:
                            ws.update("1:1", [new_header], value_input_option=self._WRITE_INPUT_OPTION)
            self._tabs_ensured.add(sheet_id)
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def ensure_tabs(self, sheet_id: str) -> None:
        await asyncio.to_thread(self._ensure_tabs_sync, sheet_id)

    def _prepare_habit_header_and_row(
        self,
        header: list[str],
        field_order: list[str],
        entry: HabitEntry,
    ) -> tuple[list[str], list[str]]:
        base_header = ["timestamp", "date", "raw_record", "diary"]
        if header:
            header = [("raw_record" if col == "raw_diary" else col) for col in header]
        else:
            header = []

        # Preserve existing custom columns to keep alignment of old rows
        canonical_header = list(header)

        for field in base_header:
            if field not in canonical_header:
                canonical_header.append(field)

        for field in field_order:
            if field not in canonical_header:
                canonical_header.append(field)

        for field in entry.extra_fields.keys():
            if field not in canonical_header:
                canonical_header.append(field)

        row = []
        for col in canonical_header:
            if col == "timestamp":
                row.append(entry.created_at.isoformat())
            elif col == "date":
                row.append(entry.date.strftime("%d-%m-%Y"))
            elif col == "raw_record":
                row.append(entry.raw_record)
            elif col == "diary":
                row.append(entry.diary or "")
            else:
                row.append(entry.extra_fields.get(col, ""))

        return canonical_header, row

    def _append_habit_entry_sync(
        self,
        sheet_id: str,
        field_order: list[str],
        entry: HabitEntry,
    ) -> None:
        try:
            self._ensure_tabs_sync(sheet_id)
            ss = self._open(sheet_id)
            ws = ss.worksheet("Habits")
            self._ensure_write_access(ws)
            header = ws.row_values(1)
            canonical_header, row = self._prepare_habit_header_and_row(header, field_order, entry)
            if header != canonical_header:
                ws.update("1:1", [canonical_header], value_input_option=self._WRITE_INPUT_OPTION)

            ws.append_row(row, value_input_option=self._WRITE_INPUT_OPTION)
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def append_habit_entry(self, sheet_id: str, field_order: list[str], entry: HabitEntry) -> None:
        await asyncio.to_thread(self._append_habit_entry_sync, sheet_id, field_order, entry)

    def _find_latest_habit_entry_sync(
        self,
        sheet_id: str,
        entry_date: date,
    ) -> HabitRowLookup | None:
        try:
            self._ensure_tabs_sync(sheet_id)
            ss = self._open(sheet_id)
            ws = ss.worksheet("Habits")
            header = ws.row_values(1)
            if not header:
                return None
            normalized = [("raw_record" if col == "raw_diary" else col) for col in header]
            if "date" not in normalized:
                return None
            date_idx = normalized.index("date")
            raw_idx = normalized.index("raw_record") if "raw_record" in normalized else None
            if raw_idx is None and "raw_diary" in normalized:
                raw_idx = normalized.index("raw_diary")

            col_letter = self._column_letter(date_idx + 1)
            values = ws.get(
                f"{col_letter}2:{col_letter}",
                value_render_option="UNFORMATTED_VALUE",
            )
            match_row = None
            for row_index, row in enumerate(values, start=2):
                value = row[0] if row else None
                parsed = self._parse_sheet_date(value)
                if parsed == entry_date:
                    match_row = row_index
            if match_row is None:
                return None
            row_values = ws.row_values(match_row)
            raw_record = ""
            if raw_idx is not None and raw_idx < len(row_values):
                raw_record = row_values[raw_idx]
            entry_data: dict[str, Any] = {}
            for idx, column in enumerate(normalized):
                entry_data[column] = row_values[idx] if idx < len(row_values) else ""
            entry_data["field_order"] = [
                col
                for col in normalized
                if col not in {"timestamp", "date", "raw_record", "diary"}
            ]
            if "raw_record" not in entry_data and raw_record:
                entry_data["raw_record"] = raw_record
            return HabitRowLookup(
                row_index=match_row,
                raw_record=raw_record,
                entry_data=entry_data,
            )
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def find_latest_habit_entry(
        self,
        sheet_id: str,
        entry_date: date,
    ) -> HabitRowLookup | None:
        return await asyncio.to_thread(self._find_latest_habit_entry_sync, sheet_id, entry_date)

    def _get_entries_for_dates_sync(
        self,
        sheet_id: str,
        dates: list[date],
        tab_name: str,
        date_column_candidates: tuple[str, ...],
        allow_multiple: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            if not dates:
                return []
            self._ensure_tabs_sync(sheet_id)
            ss = self._open(sheet_id)
            ws = ss.worksheet(tab_name)
            values = ws.get_all_values()
            if not values or len(values) < 2:
                return []
            header = values[0]
            normalized = [("raw_record" if col == "raw_diary" else col) for col in header]
            date_idx = None
            for candidate in date_column_candidates:
                if candidate in normalized:
                    date_idx = normalized.index(candidate)
                    break
            if date_idx is None:
                return []
            target_dates = set(dates)
            entries_by_date: dict[date, dict[str, Any]] = {}
            entries: list[dict[str, Any]] = []
            for row in values[1:]:
                if date_idx >= len(row):
                    continue
                parsed = self._parse_sheet_date(row[date_idx] if row else None)
                if parsed is None or parsed not in target_dates:
                    continue
                entry: dict[str, Any] = {}
                for idx, column in enumerate(normalized):
                    entry[column] = row[idx] if idx < len(row) else ""
                entry["date"] = parsed.isoformat()
                if allow_multiple:
                    entries.append(entry)
                else:
                    entries_by_date[parsed] = entry
            if allow_multiple:
                return entries
            return [entries_by_date[d] for d in dates if d in entries_by_date]
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def get_habit_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._get_entries_for_dates_sync,
            sheet_id,
            dates,
            "Habits",
            ("date",),
            False,
        )

    async def get_dream_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._get_entries_for_dates_sync,
            sheet_id,
            dates,
            "Dreams",
            ("timestamp", "date"),
            True,
        )

    async def get_thought_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._get_entries_for_dates_sync,
            sheet_id,
            dates,
            "Thoughts",
            ("timestamp", "date"),
            True,
        )

    async def get_reflection_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._get_entries_for_dates_sync,
            sheet_id,
            dates,
            "Reflections",
            ("timestamp", "date"),
            True,
        )

    def _update_habit_entry_sync(
        self,
        sheet_id: str,
        row_index: int,
        field_order: list[str],
        entry: HabitEntry,
    ) -> None:
        try:
            self._ensure_tabs_sync(sheet_id)
            ss = self._open(sheet_id)
            ws = ss.worksheet("Habits")
            self._ensure_write_access(ws)
            header = ws.row_values(1)
            canonical_header, row = self._prepare_habit_header_and_row(header, field_order, entry)
            if header != canonical_header:
                ws.update("1:1", [canonical_header], value_input_option=self._WRITE_INPUT_OPTION)
            ws.update(
                f"A{row_index}",
                [row],
                value_input_option=self._WRITE_INPUT_OPTION,
            )
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def update_habit_entry(
        self,
        sheet_id: str,
        row_index: int,
        field_order: list[str],
        entry: HabitEntry,
    ) -> None:
        await asyncio.to_thread(
            self._update_habit_entry_sync,
            sheet_id,
            row_index,
            field_order,
            entry,
        )

    def _append_dream_entry_sync(self, sheet_id: str, entry: DreamEntry) -> None:
        try:
            self._ensure_tabs_sync(sheet_id)
            ss = self._open(sheet_id)
            ws = ss.worksheet("Dreams")
            self._ensure_write_access(ws)
            row = [
                entry.timestamp.isoformat(),
                entry.record,
            ]
            ws.append_row(row, value_input_option=self._WRITE_INPUT_OPTION)
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def append_dream_entry(self, sheet_id: str, entry: DreamEntry) -> None:
        await asyncio.to_thread(self._append_dream_entry_sync, sheet_id, entry)

    def _append_thought_entry_sync(self, sheet_id: str, entry: ThoughtEntry) -> None:
        try:
            self._ensure_tabs_sync(sheet_id)
            ss = self._open(sheet_id)
            ws = ss.worksheet("Thoughts")
            self._ensure_write_access(ws)
            row = [
                entry.timestamp.isoformat(),
                entry.record,
            ]
            ws.append_row(row, value_input_option=self._WRITE_INPUT_OPTION)
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def append_thought_entry(self, sheet_id: str, entry: ThoughtEntry) -> None:
        await asyncio.to_thread(self._append_thought_entry_sync, sheet_id, entry)

    def _append_reflection_entry_sync(self, sheet_id: str, entry) -> None:
        try:
            self._ensure_tabs_sync(sheet_id)
            ss = self._open(sheet_id)
            ws = ss.worksheet("Reflections")
            self._ensure_write_access(ws)
            header = ws.row_values(1)
            canonical_header = ["timestamp", "reflections"]
            if header != canonical_header:
                ws.update("1:1", [canonical_header], value_input_option=self._WRITE_INPUT_OPTION)
            ws.append_row(
                [
                    entry.timestamp.isoformat(),
                    json.dumps(entry.answers, ensure_ascii=False),
                ],
                value_input_option=self._WRITE_INPUT_OPTION,
            )
        except Exception as exc:
            self._raise_mapped_error(exc)
            raise

    async def append_reflection_entry(self, sheet_id: str, entry) -> None:
        await asyncio.to_thread(self._append_reflection_entry_sync, sheet_id, entry)
