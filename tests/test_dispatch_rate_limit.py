"""SEC-5: /reminders/dispatch must be rate limited per user."""

import pytest
from fastapi.testclient import TestClient

from src import main as main_module
from src.core.dependencies import get_user_repo, verify_reminder_dispatch
from src.core.rate_limit import SlidingWindowRateLimiter


class StubUserRepo:
    def __init__(self) -> None:
        self.lookups: list[int] = []

    async def get_by_telegram_id(self, telegram_id: int):
        self.lookups.append(telegram_id)
        return None  # no profile -> handler returns early, before any I/O


@pytest.fixture
def client_with_limit(monkeypatch):
    """App with dispatch auth stubbed out and a 2/min dispatch limit."""

    limiter = SlidingWindowRateLimiter(2, window_seconds=60, clock=lambda: 100.0)
    monkeypatch.setattr(main_module, "get_dispatch_rate_limiter", lambda: limiter)

    repo = StubUserRepo()
    main_module.app.dependency_overrides[verify_reminder_dispatch] = lambda: True
    main_module.app.dependency_overrides[get_user_repo] = lambda: repo
    try:
        yield TestClient(main_module.app), repo
    finally:
        main_module.app.dependency_overrides.clear()


def test_dispatch_rate_limits_per_user(client_with_limit):
    client, repo = client_with_limit

    for _ in range(2):
        response = client.post("/reminders/dispatch", json={"user_id": 42})
        assert response.status_code == 200

    blocked = client.post("/reminders/dispatch", json={"user_id": 42})
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limited"
    # The blocked request must not reach storage.
    assert repo.lookups == [42, 42]


def test_dispatch_rate_limit_is_per_user(client_with_limit):
    client, _repo = client_with_limit

    for _ in range(2):
        assert client.post("/reminders/dispatch", json={"user_id": 1}).status_code == 200
    assert client.post("/reminders/dispatch", json={"user_id": 1}).status_code == 429
    # A different user still gets their own budget.
    assert client.post("/reminders/dispatch", json={"user_id": 2}).status_code == 200


def test_dispatch_rejects_missing_user_id_before_rate_limiting(client_with_limit):
    client, _repo = client_with_limit

    response = client.post("/reminders/dispatch", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "user_id_missing"
