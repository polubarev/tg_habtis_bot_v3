from typing import Optional

try:
    from google.cloud import firestore
    from google.oauth2 import service_account
except Exception:  # pragma: no cover - optional dependency
    firestore = None
    service_account = None

from src.core.logging import get_logger

logger = get_logger(__name__)


class FirestoreClient:
    """Lightweight Firestore client wrapper."""

    def __init__(self, credentials_path: Optional[str] = None, project_id: Optional[str] = None):
        self._client = None
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.service_email: str | None = None
        if firestore is None:
            logger.warning("google.cloud.firestore not available; falling back to in-memory stores")
            return
        try:
            if credentials_path and service_account is not None:
                creds = service_account.Credentials.from_service_account_file(credentials_path)
                self.service_email = creds.service_account_email
                self._client = firestore.Client(project=project_id, credentials=creds)
            else:
                self._client = firestore.Client(project=project_id)
            logger.info(
                "Firestore client initialized",
                project=project_id,
                credentials_path=credentials_path,
                service_email=self.service_email,
            )
        except Exception as exc:  # pragma: no cover - external dependency
            logger.warning(
                "Failed to initialize Firestore client; using in-memory stores",
                error=str(exc),
                project=project_id,
                credentials_path=credentials_path,
            )
            self._client = None

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    def collection(self, name: str):
        if not self._client:
            raise RuntimeError("Firestore client is not configured")
        return self._client.collection(name)
