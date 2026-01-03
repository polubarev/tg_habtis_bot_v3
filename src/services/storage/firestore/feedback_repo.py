from src.config.settings import get_settings
from src.core.logging import get_logger
from src.models.feedback import FeedbackEntry
from src.services.storage.firestore.client import FirestoreClient

logger = get_logger(__name__)


class FeedbackRepository:
    """Firestore implementation for storing feedback entries."""

    def __init__(self, client: FirestoreClient | None = None):
        self.client = client
        settings = get_settings()
        self.collection_name = settings.firestore_collection_feedback

    async def create(self, entry: FeedbackEntry) -> bool:
        if self.client and self.client.is_ready:
            try:
                data = entry.model_dump(mode="json")
                self.client.collection(self.collection_name).document().set(data)
                return True
            except Exception as exc:
                logger.warning(
                    "Firestore unavailable for feedback; skipping save",
                    error=str(exc),
                )
                self.client = None
        return False
