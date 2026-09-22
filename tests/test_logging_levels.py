import logging

from src.core.logging import setup_logging


def test_content_bearing_sdk_loggers_are_never_debug():
    setup_logging("DEBUG")

    for name in ("openai", "openai._base_client", "langchain", "urllib3"):
        assert logging.getLogger(name).level >= logging.WARNING
