"""Structured analytics events for bot usage dashboards.

Every event is emitted as a single structlog INFO record with the message
``bot_event`` and a stable set of top-level fields. The Cloud Logging sink
filters on ``jsonPayload.event = "bot_event"`` to populate the BigQuery
table that backs the Looker Studio dashboard. See docs/analytics.md.
"""

from __future__ import annotations

from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger("bot.analytics")


def log_event(name: str, *, user_id: Optional[int] = None, **props: Any) -> None:
    """Emit a single analytics event line.

    ``name`` is the dotted action label (e.g. ``command.habits``,
    ``llm.call``). ``props`` become flat top-level JSON fields, so keep
    keys low-cardinality and BigQuery-friendly (snake_case, scalars).
    """

    payload: dict[str, Any] = {"name": name}
    if user_id is not None:
        payload["user_id"] = user_id
    for key, value in props.items():
        if value is None:
            continue
        payload[key] = value
    logger.info("bot_event", **payload)
