from datetime import date, timezone

from src.models.entry import HabitEntry
from src.models.feedback import FeedbackEntry
from src.models.user import UserProfile


def test_model_timestamp_defaults_are_timezone_aware_utc():
    habit = HabitEntry(date=date(2026, 7, 26), raw_record="walk")
    feedback = FeedbackEntry(telegram_user_id=1, message="Great")
    user = UserProfile(telegram_user_id=1)

    timestamps = [
        habit.created_at,
        feedback.created_at,
        user.created_at,
        user.updated_at,
    ]
    assert all(timestamp.tzinfo is timezone.utc for timestamp in timestamps)
