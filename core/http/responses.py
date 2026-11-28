"""JSON request and response helpers shared by every blueprint."""

import functools
import uuid

from flask import jsonify, request

from core.errors import ServiceError
from core.log import get_logger

logger = get_logger(__name__)


def json_body() -> dict:
    """The request's JSON object, or an empty dict when the body is missing or not an object."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def error(message: str, status: int, key: str = "error"):
    """A JSON error response: ({key: message}, status)."""
    return jsonify({key: message}), status


def internal_error(where: str, key: str = "error", **fields: str):
    """A 500 with an error id and fields, and no exception text. Call it in an except block: it logs the traceback."""
    error_id = uuid.uuid4().hex[:12]
    logger.exception("unhandled error in %s error_id=%s", where, error_id)
    message = f"Something went wrong on the server (error id {error_id})"
    return jsonify({**fields, key: message, "error_id": error_id}), 500


def error_handler(f):
    """Turn a ServiceError into its message and status, and any other exception into internal_error."""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ServiceError as e:
            return error(e.message, e.status)
        except Exception:
            return internal_error(f.__name__)

    return wrapper
