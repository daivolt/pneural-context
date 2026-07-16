from __future__ import annotations

import json
import logging

from pneural_context.logging import JSONFormatter, setup_logging


def test_json_formatter_basic():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=None,
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["message"] == "test message"
    assert "timestamp" in data


def test_json_formatter_with_exception():
    formatter = JSONFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys

        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="error occurred",
        args=None,
        exc_info=exc_info,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "ERROR"
    assert "exception" in data


def test_setup_logging():
    setup_logging("DEBUG")
    logger = logging.getLogger("pneural_context")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler.formatter, JSONFormatter)


def test_setup_logging_info_level():
    setup_logging("INFO")
    logger = logging.getLogger("pneural_context")
    assert logger.level == logging.INFO
