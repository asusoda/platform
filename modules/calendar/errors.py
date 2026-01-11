import logging
from dataclasses import dataclass
from typing import Optional
from notion_client import APIErrorCode, APIResponseError
from googleapiclient.errors import HttpError
from sentry_sdk import capture_exception, set_tag, set_context

# Assuming logger is configured elsewhere, e.g., in shared.py
# If not, initialize a default logger:
# logger = logging.getLogger(__name__)


@dataclass
class ErrorResult:
    """Result of error handling with retry guidance."""
    should_retry: bool = False
    retry_after: Optional[int] = None  # Seconds to wait before retry
    is_rate_limit: bool = False
    error_type: str = "unknown"


class APIErrorHandler:
    """Standardized error handling for API operations with retry guidance."""

    def __init__(self, logger, operation_name, transaction=None):
        self.logger = logger
        self.operation_name = operation_name
        self.transaction = transaction # Optional transaction context for Sentry

    def handle_http_error(self, error: HttpError, context_data=None) -> ErrorResult:
        """Handle HttpError consistently with retry guidance.
        
        Returns:
            ErrorResult with retry guidance for rate limits and transient errors.
        """
        capture_exception(error)
        details = getattr(error, 'error_details', str(error)) # Get details if available
        status = error.resp.status if hasattr(error, 'resp') else 'Unknown'
        self.logger.error(f"HTTP error during {self.operation_name}: {status} - {details}")

        error_context = {
            "status": status,
            "details": details,
            **(context_data or {})
        }
        set_context("http_error", error_context)
        
        result = ErrorResult(error_type="http_error")

        if hasattr(error, 'resp'):
            if error.resp.status == 404:
                set_tag("error_type", "not_found")
                result.error_type = "not_found"
            elif error.resp.status == 403:
                # Check if it's a rate limit error (Google returns 403 for quota exceeded)
                error_str = str(error).lower()
                if 'rate limit' in error_str or 'quota' in error_str or 'userRateLimitExceeded' in str(details):
                    set_tag("error_type", "rate_limited")
                    result.error_type = "rate_limited"
                    result.should_retry = True
                    result.is_rate_limit = True
                    result.retry_after = 60  # Default 60 seconds for rate limits
                    self.logger.warning(f"Rate limit hit during {self.operation_name}, should retry after {result.retry_after}s")
                else:
                    set_tag("error_type", "permission_denied")
                    result.error_type = "permission_denied"
            elif error.resp.status == 429:
                # Explicit rate limit status
                set_tag("error_type", "rate_limited")
                result.error_type = "rate_limited"
                result.should_retry = True
                result.is_rate_limit = True
                # Try to extract Retry-After header
                retry_after = error.resp.get('retry-after')
                result.retry_after = int(retry_after) if retry_after else 60
                self.logger.warning(f"Rate limit (429) during {self.operation_name}, retry after {result.retry_after}s")
            elif error.resp.status in (500, 502, 503, 504):
                # Server errors - should retry
                set_tag("error_type", "server_error")
                result.error_type = "server_error"
                result.should_retry = True
                result.retry_after = 5
                self.logger.warning(f"Server error ({status}) during {self.operation_name}, should retry")
            else:
                set_tag("error_type", "http_error")
        else:
             set_tag("error_type", "http_error_unknown_status")
        
        return result

    def handle_notion_error(self, error: APIResponseError, context_data=None) -> ErrorResult:
        """Handle Notion API errors consistently with retry guidance.
        
        Returns:
            ErrorResult with retry guidance for rate limits.
        """
        capture_exception(error)
        self.logger.error(f"Notion API Error during {self.operation_name}: {error.code} - {str(error)}")
        set_context("notion_error", {
            "code": error.code,
            "message": str(error),
            **(context_data or {})
        })
        
        result = ErrorResult(error_type="notion_api_error")

        if error.code == APIErrorCode.ObjectNotFound:
            set_tag("error_type", "database_not_found") # Or object_not_found depending on context
            result.error_type = "database_not_found"
        elif error.code == APIErrorCode.Unauthorized:
            set_tag("error_type", "notion_unauthorized")
            result.error_type = "notion_unauthorized"
        elif error.code == APIErrorCode.RateLimited:
            set_tag("error_type", "notion_rate_limited")
            result.error_type = "notion_rate_limited"
            result.should_retry = True
            result.is_rate_limit = True
            result.retry_after = 30  # Notion typically needs ~30s cooldown
            self.logger.warning(f"Notion rate limit during {self.operation_name}, should retry after {result.retry_after}s")
        else:
            set_tag("error_type", "notion_api_error")
        
        return result

    def handle_generic_error(self, error: Exception, context_data=None) -> ErrorResult:
        """Handle general exceptions consistently.
        
        Returns:
            ErrorResult (non-retryable by default for unknown errors).
        """
        capture_exception(error)
        self.logger.error(f"Unexpected error during {self.operation_name}: {str(error)}")
        set_tag("error_type", "unexpected")
        if context_data:
            set_context("error_context", context_data)
        
        # Check for connection/timeout errors which may be transient
        error_str = str(error).lower()
        result = ErrorResult(error_type="unexpected")
        
        if any(term in error_str for term in ['timeout', 'timed out', 'connection', 'ssl', 'tls']):
            result.should_retry = True
            result.retry_after = 5
            result.error_type = "connection_error"
            self.logger.warning(f"Connection/timeout error during {self.operation_name}, should retry")
        
        return result