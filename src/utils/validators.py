
from typing import Iterable


def ensure_required_fields(data: dict, required: Iterable[str]) -> None:
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
