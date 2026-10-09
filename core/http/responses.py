"""JSON request and response helpers shared by every blueprint."""

import functools

from flask import jsonify, request

from core.log import get_logger

logger = get_logger(__name__)


def json_body() -> dict:
    """The request's JSON object, or an empty dict when the body is missing or not an object."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def error(message: str, status: int, key: str = "error"):
    """A JSON error response: ({key: message}, status)."""
    return jsonify({key: message}), status


def error_handler(f):
    """Turn an unhandled exception in a view into {"error": str(e)} with status 500."""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return error(str(e), 500)

    return wrapper
