"""Notion API client for an org's events database. An org can bring its own integration token."""

from notion_client import APIResponseError
from notion_client import Client as NotionClient
from notion_client.helpers import collect_paginated_api
from sentry_sdk import capture_exception, set_context, start_transaction

from core.config import config
from core.log import get_logger

from ..errors import APIErrorHandler
from ..tracing import operation_span

logger = get_logger(__name__)


class NotionCalendarClient:
    """Client for Notion calendar-related operations."""

    def __init__(self, logger_instance=None, token: str | None = None):
        self.logger = logger_instance or logger
        # An org's own integration token if given, else the instance-wide NOTION_API_KEY
        self.notion: NotionClient = NotionClient(auth=token or config.NOTION_API_KEY)
        self.error_handler = APIErrorHandler(self.logger, "NotionCalendarClient")

    def fetch_events(self, database_id: str, parent_transaction=None) -> list[dict] | None:
        """Fetch published events from Notion with pagination and error handling."""
        op_name = "fetch_notion_events"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="notion", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="notion_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            context_data = {"database_id": database_id}
            set_context("notion_query", context_data)
            self.logger.info(f"Fetching all published Notion events from database {database_id} using pagination.")

            try:
                query_filter = {
                    "property": "Published",
                    "checkbox": {"equals": True},
                }

                with operation_span(
                    transaction, op="api_call", description="notion.data_sources.query", logger=self.logger
                ) as span:
                    all_events = collect_paginated_api(
                        self.notion.data_sources.query,
                        data_source_id=database_id,
                        filter=query_filter,
                    )
                    span.set_data("event_count", len(all_events))

                self.logger.info(
                    f"Fetched a total of {len(all_events)} Notion events via pagination from {database_id}."
                )
                return all_events

            except APIResponseError as error:
                return self.error_handler.handle_notion_error(error, context_data)
            except Exception as e:
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None

    def update_page_with_gcal_id(
        self, page_id: str, gcal_id: str, gcal_link: str | None = None, parent_transaction=None
    ) -> bool:
        """Update Notion page with Google Calendar ID and optionally the HTML link."""
        op_name = "update_notion_page_gcal_id"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="notion", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="notion_api", description=op_name, logger=self.logger
        ) as transaction:
            context_data = {"notion_page_id": page_id, "gcal_id": gcal_id, "gcal_link": gcal_link}
            set_context("notion_update", context_data)

            properties_to_update = {"gcal_id": {"rich_text": [{"type": "text", "text": {"content": gcal_id}}]}}
            if gcal_link:
                gcal_link_property = getattr(config, "NOTION_GCAL_LINK_PROPERTY", None)
                if gcal_link_property:
                    properties_to_update[gcal_link_property] = {"url": gcal_link}
                else:
                    self.logger.info(
                        f"Skipping adding Google Calendar link to Notion page {page_id}: NOTION_GCAL_LINK_PROPERTY not configured"
                    )

            try:
                with operation_span(
                    transaction, op="api_call", description="notion.pages.update", logger=self.logger
                ) as span:
                    self.notion.pages.update(page_id=page_id, properties=properties_to_update)
                    span.set_data("update_success", True)
                    self.logger.info(
                        f"Successfully updated Notion page {page_id} with GCAL ID {gcal_id}"
                        + (f" and link {gcal_link}" if gcal_link else "")
                    )
                    return True

            except APIResponseError as e:
                capture_exception(e)
                self.logger.error(
                    f"Notion API error updating page {page_id} with GCAL ID {gcal_id}: {e.code} - {str(e)}"
                )
                set_context("notion_error", {"code": e.code, "message": str(e), **context_data})
                transaction.set_status("internal_error")
                return False
            except Exception as e:
                capture_exception(e)
                self.logger.error(f"Unexpected error updating Notion page {page_id} with GCAL ID {gcal_id}: {str(e)}")
                set_context("unexpected_error", {"error": str(e), **context_data})
                transaction.set_status("internal_error")
                return False
