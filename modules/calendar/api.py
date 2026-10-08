"""HTTP routes for the calendar. The logic is in service.py; these only translate to and from HTTP."""

from flask import Blueprint, jsonify
from sentry_sdk import set_tag, start_transaction

from core.db import db_connect
from core.logging_config import get_logger
from modules.auth.access import any_officer_denial
from modules.auth.decoraters import auth_required
from modules.organizations.models import Organization

from . import service
from .errors import APIErrorHandler

logger = get_logger(__name__)

route_error_handler = APIErrorHandler(logger, "CalendarAPI_Route")

calendar_blueprint = Blueprint("calendar", __name__)


@calendar_blueprint.route("/debug/organizations", methods=["GET"])
def debug_organizations():
    """Debug endpoint to list all organizations."""
    denial = any_officer_denial()
    if denial:
        return jsonify({"message": denial[0]}), denial[1]
    try:
        with next(db_connect.get_db()) as session:
            orgs = session.query(Organization).filter(Organization.is_active).all()
            org_list = [{"id": org.id, "name": org.name, "prefix": org.prefix} for org in orgs]
            return jsonify({"status": "success", "organizations": org_list, "count": len(org_list)})
    except Exception as e:
        logger.error(f"Error in debug_organizations: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@calendar_blueprint.route("/<org_prefix>/events", methods=["GET"])
def get_organization_events(org_prefix):
    """
    Public endpoint to get events for a specific organization.
    Accessible via: /api/calendar/{org_prefix}/events
    """
    transaction = start_transaction(op="api", name="get_org_events")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "get_org_events"
    logger.info(f"Received GET request for organization events: {org_prefix}")
    set_tag("request_type", "GET")
    set_tag("organization_prefix", org_prefix)

    try:
        with next(db_connect.get_db()) as session:
            try:
                org = service.find_organization(session, org_prefix)
                events_result = service.list_events(session, org, transaction)
            except service.CalendarError as e:
                logger.warning(e.message)
                return jsonify({"status": "error", "message": e.message}), e.status

            if events_result.get("status") == "error":
                logger.error(f"Failed to get events for org {org_prefix}: {events_result.get('message')}")
                return jsonify(events_result), 500
            else:
                logger.info(f"Successfully prepared {len(events_result.get('events', []))} events for org {org_prefix}")
                return jsonify(events_result), 200

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()


@calendar_blueprint.route("/<org_prefix>/sync", methods=["POST"])
@auth_required
def sync_organization_calendar(org_prefix):
    """
    Admin endpoint to sync Notion to Google Calendar for a specific organization.
    Accessible via: /api/calendar/{org_prefix}/sync
    Requires authentication.
    """
    transaction = start_transaction(op="admin", name="sync_org_calendar")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "sync_org_calendar"
    logger.info(f"Received POST request to sync organization calendar: {org_prefix}")
    set_tag("request_type", "POST")
    set_tag("organization_prefix", org_prefix)

    try:
        with next(db_connect.get_db()) as session:
            # Get organization by prefix
            org = session.query(Organization).filter(Organization.prefix == org_prefix, Organization.is_active).first()

            if not org:
                logger.warning(f"Organization with prefix '{org_prefix}' not found or inactive")
                return jsonify({"status": "error", "message": "Organization not found"}), 404

            sync_result = service.sync_organization(session, org, transaction)

            if sync_result.get("status") == "error":
                logger.error(f"Failed to sync org {org_prefix}: {sync_result.get('message')}")
                return jsonify(sync_result), 500
            else:
                logger.info(f"Successfully synced calendar for org {org_prefix}")
                return jsonify(sync_result), 200

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()


@calendar_blueprint.route("/<org_prefix>/setup", methods=["POST"])
@auth_required
def setup_organization_calendar(org_prefix):
    """
    Admin endpoint to set up calendar for a new organization.
    Accessible via: /api/calendar/{org_prefix}/setup
    Requires authentication.
    """
    transaction = start_transaction(op="admin", name="setup_org_calendar")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "setup_org_calendar"
    logger.info(f"Received POST request to setup organization calendar: {org_prefix}")
    set_tag("request_type", "POST")
    set_tag("organization_prefix", org_prefix)

    try:
        with next(db_connect.get_db()) as session:
            # Get organization by prefix
            org = session.query(Organization).filter(Organization.prefix == org_prefix, Organization.is_active).first()

            if not org:
                logger.warning(f"Organization with prefix '{org_prefix}' not found or inactive")
                return jsonify({"status": "error", "message": "Organization not found"}), 404

            calendar_id = service.setup_calendar(session, org, transaction)

            if calendar_id:
                logger.info(f"Successfully set up calendar {calendar_id} for org {org_prefix}")
                return jsonify(
                    {
                        "status": "success",
                        "message": f"Calendar set up for organization {org_prefix}",
                        "calendar_id": calendar_id,
                        "organization_id": org.id,
                    }
                ), 200
            else:
                logger.error(f"Failed to set up calendar for org {org_prefix}")
                return jsonify({"status": "error", "message": "Failed to set up calendar"}), 500

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()


@calendar_blueprint.route("/sync-all", methods=["POST"])
@auth_required
def sync_all_organizations():
    """
    Admin endpoint to sync all organizations with calendar sync enabled.
    Accessible via: /api/calendar/sync-all
    Requires authentication.
    """
    transaction = start_transaction(op="admin", name="sync_all_organizations")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "sync_all_organizations"
    logger.info("Received POST request to sync all organizations")
    set_tag("request_type", "POST")

    try:
        # Sync all organizations using multi-org service
        sync_result = service.sync_all(transaction)

        if sync_result.get("status") == "error":
            logger.error(f"Failed to sync all organizations: {sync_result.get('message')}")
            return jsonify(sync_result), 500
        else:
            logger.info(f"Successfully synced {sync_result.get('organizations_processed', 0)} organizations")
            return jsonify(sync_result), 200

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()


# Legacy endpoints for backward compatibility (deprecated)
@calendar_blueprint.route("/notion-webhook", methods=["POST"])
def notion_webhook():
    """
    Legacy webhook endpoint - now delegates to sync-all.
    """
    logger.warning("Legacy /notion-webhook endpoint called. This will sync all organizations.")
    return sync_all_organizations()


@calendar_blueprint.route("/events", methods=["GET"])
def get_calendar_events_for_frontend():
    """
    Legacy endpoint - returns error as this requires organization context.
    """
    return jsonify(
        {
            "status": "error",
            "message": "This endpoint requires organization context. Use /api/calendar/{org_prefix}/events instead.",
        }
    ), 400


@calendar_blueprint.route("/delete-all-events", methods=["POST"])
def delete_all_calendar_events():
    """
    Legacy endpoint - returns error as this requires organization context.
    """
    return jsonify(
        {
            "status": "error",
            "message": "This endpoint requires organization context. Use organization-specific endpoints instead.",
        }
    ), 400
