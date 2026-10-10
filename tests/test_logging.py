"""LOG_FORMAT=json writes one JSON object per line and lifts request and access fields."""

import json
import logging

from core.log import JsonFormatter


def _format(name, message):
    record = logging.LogRecord(name, logging.INFO, __file__, 1, message, None, None)
    return json.loads(JsonFormatter().format(record))


def test_request_line_fields_are_lifted():
    entry = _format("request_log", "request method=GET route=/api/x status=200 org=soda discord_id=None")
    assert entry["level"] == "INFO"
    assert entry["route"] == "/api/x"
    assert entry["status"] == "200"
    assert entry["discord_id"] is None


def test_other_loggers_keep_the_message_only():
    entry = _format("modules.points", "awarded points=5")
    assert entry["msg"] == "awarded points=5"
    assert "points" not in entry
