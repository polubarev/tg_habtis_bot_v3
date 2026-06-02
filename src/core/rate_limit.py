from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable


class SlidingWindowRateLimiter:
    """In-memory per-key sliding window rate limiter."""

    def __init__(
        self,
        limit: int,
        *,
        window_seconds: int = 60,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.limit = max(0, limit)
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._requests: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, key: int) -> bool:
        if self.limit <= 0:
            return False

        now = self._clock()
        cutoff = now - self.window_seconds
        bucket = self._requests[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            return False

        bucket.append(now)
        return True
