
from typing import Optional


class SheetsClient:
    """Placeholder Google Sheets client wrapper."""

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path
        self.client = None
        if credentials_path:
            try:
                import gspread  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("gspread is not installed") from exc
            self.client = gspread.service_account(filename=credentials_path)

    def open_sheet(self, sheet_id: str):
        if not self.client:
            raise RuntimeError("Sheets client is not configured")
        return self.client.open_by_key(sheet_id)
