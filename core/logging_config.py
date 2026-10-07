import json
import logging
import os
import re

import colorlog

# key=value pairs in the request_log and access lines, lifted into JSON fields
_PAIR = re.compile(r"(\w+)=(\S+)")
_STRUCTURED_LOGGERS = {"request_log", "access"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for log collectors. Selected with LOG_FORMAT=json."""

    def format(self, record):
        message = record.getMessage()
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": message,
        }
        if record.name in _STRUCTURED_LOGGERS:
            entry.update({k: (None if v == "None" else v) for k, v in _PAIR.findall(message)})
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


# Configure logging with colors and improved formatting
def setup_logger():
    """Configure and return the root logger: colored text by default, JSON lines with LOG_FORMAT=json"""
    if os.environ.get("LOG_FORMAT", "").lower() == "json":
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
    else:
        handler = colorlog.StreamHandler()
        formatter = colorlog.ColoredFormatter(
            fmt="%(log_color)s[%(asctime)s] %(levelname)-8s %(name)-20s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for hdlr in root_logger.handlers:
        root_logger.removeHandler(hdlr)

    root_logger.addHandler(handler)
    return root_logger


# Initialize root logger
logger = setup_logger()


def get_logger(name):
    """Get a logger for a specific module with proper formatting"""
    return logging.getLogger(name)
