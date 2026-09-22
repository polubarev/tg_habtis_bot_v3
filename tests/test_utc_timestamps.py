from datetime import date, timezone

from src.models.entry import HabitEntry
from src.models.feedback import FeedbackEntry
from src.models.transcription_batch import TranscriptionBatch
from src.models.user import UserProfile


def test_model_timestamp_defaults_are_timezone_aware_utc():
    habit = HabitEntry(date=date(2026, 7, 26), raw_record="walk")
    feedback = FeedbackEntry(telegram_user_id=1, message="Great")
    transcription_batch = TranscriptionBatch(user_id=1, chat_id=1)
    user = UserProfile(telegram_user_id=1)

    timestamps = [
        habit.created_at,
        feedback.created_at,
        transcription_batch.created_at,
        transcription_batch.updated_at,
        transcription_batch.expires_at,
        user.created_at,
        user.updated_at,
    ]
    assert all(timestamp.tzinfo is timezone.utc for timestamp in timestamps)
