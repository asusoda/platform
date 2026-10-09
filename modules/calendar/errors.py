"""Logging and Sentry reporting for Google and Notion API errors."""

from googleapiclient.errors import HttpError
from notion_client import APIErrorCode, APIResponseError
from sentry_sdk import capture_exception, set_context, set_tag


class APIErrorHandler:
    """Logs an API error, sends it to Sentry with an error_type tag, and returns None."""

    def __init__(self, logger, operation_name, transaction=None):
        self.logger = logger
        self.operation_name = operation_name
        self.transaction = transaction

    def handle_http_error(self, error: HttpError, context_data=None):
        """Report a Google HttpError, tagged not_found, permission_denied or http_error."""
        capture_exception(error)
        details = getattr(error, "error_details", str(error))
        status = error.resp.status if hasattr(error, "resp") else "Unknown"
        self.logger.error(f"HTTP error during {self.operation_name}: {status} - {details}")

        error_context = {"status": status, "details": details, **(context_data or {})}
        set_context("http_error", error_context)

        if hasattr(error, "resp"):
            if error.resp.status == 404:
                set_tag("error_type", "not_found")
            elif error.resp.status == 403:
                set_tag("error_type", "permission_denied")
            else:
                set_tag("error_type", "http_error")
        else:
            set_tag("error_type", "http_error_unknown_status")
        return None

    def handle_notion_error(self, error: APIResponseError, context_data=None):
        """Report a Notion APIResponseError, tagged by its error code."""
        capture_exception(error)
        self.logger.error(f"Notion API Error during {self.operation_name}: {error.code} - {str(error)}")
        set_context("notion_error", {"code": error.code, "message": str(error), **(context_data or {})})

        if error.code == APIErrorCode.ObjectNotFound:
            set_tag("error_type", "database_not_found")
        elif error.code == APIErrorCode.Unauthorized:
            set_tag("error_type", "notion_unauthorized")
        elif error.code == APIErrorCode.RateLimited:
            set_tag("error_type", "notion_rate_limited")
        else:
            set_tag("error_type", "notion_api_error")
        return None

    def handle_generic_error(self, error: Exception, context_data=None):
        """Report any other exception, tagged unexpected."""
        capture_exception(error)
        self.logger.error(f"Unexpected error during {self.operation_name}: {str(error)}")
        set_tag("error_type", "unexpected")
        if context_data:
            set_context("error_context", context_data)
        return None
