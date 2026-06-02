from src.core.rate_limit import SlidingWindowRateLimiter
from src.services.telegram.bot import _extract_update_user_id


def test_sliding_window_rate_limiter_rejects_after_limit():
    current = 100.0
    limiter = SlidingWindowRateLimiter(2, window_seconds=60, clock=lambda: current)

    assert limiter.allow(1) is True
    assert limiter.allow(1) is True
    assert limiter.allow(1) is False


def test_sliding_window_rate_limiter_allows_after_window():
    current = 100.0
    limiter = SlidingWindowRateLimiter(1, window_seconds=60, clock=lambda: current)

    assert limiter.allow(1) is True
    current = 161.0
    assert limiter.allow(1) is True


def test_sliding_window_rate_limiter_is_per_key():
    limiter = SlidingWindowRateLimiter(1, window_seconds=60, clock=lambda: 100.0)

    assert limiter.allow(1) is True
    assert limiter.allow(2) is True
    assert limiter.allow(1) is False


def test_extract_update_user_id_from_message():
    payload = {"message": {"from": {"id": 123}}}

    assert _extract_update_user_id(payload) == 123


def test_extract_update_user_id_from_callback_query():
    payload = {"callback_query": {"from": {"id": 456}}}

    assert _extract_update_user_id(payload) == 456
