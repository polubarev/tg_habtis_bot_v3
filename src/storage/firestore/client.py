
from typing import Optional


def get_firestore_client(project_id: Optional[str]):
    """Lazy import Firestore client to avoid hard dependency during early setup."""

    if not project_id:
        return None
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("google-cloud-firestore is not installed") from exc
    return firestore.Client(project=project_id)
