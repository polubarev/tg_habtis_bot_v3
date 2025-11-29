
import os
from typing import Optional


def get_secret_from_env(key: str) -> Optional[str]:
    """Temporary secret loader until Secret Manager integration is added."""

    return os.getenv(key)
