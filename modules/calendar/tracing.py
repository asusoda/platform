"""Sentry spans for calendar operations."""

import logging
from contextlib import contextmanager

from sentry_sdk import capture_exception


@contextmanager
def operation_span(transaction, op, description, logger=None):
    """A child span of transaction. An error is logged, sent to Sentry, set on the span and raised again."""
    current_logger = logger if logger else logging.getLogger(__name__)

    span = transaction.start_child(op=op, description=description)
    try:
        yield span
    except Exception as e:
        current_logger.error(f"Error in operation {description}: {str(e)}")
        capture_exception(e)
        try:
            span.set_data("error", str(e))
            span.set_status("internal_error")
        except Exception as data_err:
            current_logger.error(f"Failed to set error data on span {description}: {data_err}")
        raise
    finally:
        try:
            span.finish()
        except Exception as finish_err:
            current_logger.error(f"Failed to finish span {description}: {finish_err}")
