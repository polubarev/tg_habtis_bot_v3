
from typing import Optional


def get_sheets_client(credentials_path: Optional[str]):
    """Lazy import Sheets client to avoid hard dependency during early setup."""

    if not credentials_path:
        return None
    try:
        import gspread  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("gspread is not installed") from exc
    return gspread.service_account(filename=credentials_path)
