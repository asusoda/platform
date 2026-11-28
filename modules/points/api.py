"""Officer routes of points: members, point entries, awards and the attendance CSV imports.

The member and public routes (store sign-in, member profile, leaderboard) are in member_api.py.
"""

from flask import Blueprint, jsonify, request

from core.db import db_connect
from core.http.cached import cached_json, org_key
from core.http.responses import json_body
from core.log import get_logger
from modules.auth.access import awarded_by, is_org_officer
from modules.auth.decorators import auth_required
from modules.auth.routes import officer_route
from modules.organizations import service as organizations
from modules.points import service
from modules.points.submodules.checkins import csv_import

logger = get_logger(__name__)

points_blueprint = Blueprint("points", __name__, template_folder=None, static_folder=None)

# Writes in this process drop the officer lists at once; writes elsewhere drop them through core.cache.publish
OFFICER_LIST_TTL = 30  # seconds

ORG_NOT_FOUND = "Organization not found"


def active_org(db, org_prefix):
    return organizations.find_by_prefix(db, org_prefix, active_only=True)


@officer_route(points_blueprint, "/users", ["POST"])
def manage_user(db, org):
    """Create, update or link a member of the org."""
    body, created = service.save_member(db, org, json_body())
    return body, 201 if created else 200


@points_blueprint.route("/<string:org_prefix>/add_points", methods=["POST"])
@auth_required
def add_points_to_org(org_prefix):
    """Add points to a member found by Discord id, else by email, uuid or username. An unknown org gets 400."""
    db = db_connect.SessionLocal()
    try:
        organization = active_org(db, org_prefix)
        if not organization:
            return jsonify({"error": ORG_NOT_FOUND}), 400
        data = json_body()
        point = service.add_points(db, organization.id, data, awarded_by(data.get("awarded_by_officer")))
        return jsonify(point), 201
    except service.PointsError as e:
        return jsonify({"error": e.message}), e.status
    except Exception:
        db.rollback()
        logger.exception("add_points failed org=%s", org_prefix)
        return jsonify({"error": "An error occurred while adding points"}), 400
    finally:
        db.close()


@officer_route(points_blueprint, "/users", ["GET"])
def get_org_users(db, org):
    """The org's active members with their points."""
    organization_id = org.id
    organization_json = {"name": org.name, "prefix": org.prefix, "description": org.description}

    def build():
        users_data = service.members_with_points(db, organization_id)
        return {"organization": organization_json, "total_users": len(users_data), "users": users_data}

    return cached_json(org_key(org.prefix, "points", "users"), OFFICER_LIST_TTL, build)


@officer_route(points_blueprint, "/get_points", ["GET"])
def get_org_points(db, org):
    """Every point entry in the org."""
    organization_id = org.id
    return cached_json(
        org_key(org.prefix, "points", "entries"), OFFICER_LIST_TTL, lambda: service.all_entries(db, organization_id)
    )


@officer_route(points_blueprint, "/uploadEventCSV", ["POST"])
def upload_event_csv(db, org):
    """Add a CSV import run and queue the points.import_event_csv job for it. 202 with the run's id."""
    if "file" not in request.files or "event_name" not in request.form or "event_points" not in request.form:
        return {"error": "Missing required fields"}, 400
    file = request.files["file"]
    raw = file.stream.read(csv_import.MAX_UPLOAD_BYTES + 1)
    run = csv_import.queue_upload(
        db, org, file.filename, raw, request.form["event_name"], request.form["event_points"], awarded_by(None)
    )
    return {"message": "File is being processed in the background.", "import_id": run.id}, 202


@officer_route(points_blueprint, "/imports", ["GET"])
def list_imports(db, org):
    """The org's newest 20 CSV import runs."""
    return {"imports": csv_import.runs(db, org.id)}


@officer_route(points_blueprint, "/imports/<int:import_id>", ["GET"])
def get_import(db, org, import_id):
    """One CSV import run of the org, with its progress and row errors."""
    run = csv_import.run(db, org.id, import_id)
    if run is None:
        return {"error": "Import not found"}, 404
    return csv_import.run_json(run)


@officer_route(points_blueprint, "/assign_points", ["POST"])
def assign_points_to_org(db, org):
    """Add points to an active member found by email, uuid or username."""
    data = json_body()
    return service.assign(db, org, data, awarded_by(data.get("awarded_by_officer"))), 201


@officer_route(points_blueprint, "/delete_points", ["DELETE"])
def delete_points_by_event(db, org):
    """Delete a member's first entry for an event in the org."""
    return service.delete_event_points(db, org.id, json_body())


@officer_route(points_blueprint, "/entries/<int:entry_id>", ["DELETE"])
def delete_entry(db, org, entry_id):
    """Delete one point entry of the org by its id. An entry of another org is not found."""
    return {"message": "Points deleted successfully", "deleted_points": service.delete_entry(db, org.id, entry_id)}


@officer_route(points_blueprint, "/users/<string:user_identifier>", ["PUT", "PATCH"])
def update_user_fields_endpoint(db, org, user_identifier):
    """Update the fields sent for an active member. Legacy keys name their columns."""
    body = service.update_member_fields(db, org.id, user_identifier, json_body())
    return body, 400 if "details" in body else 200


@officer_route(points_blueprint, "/users/<string:user_identifier>/points", ["GET"])
def get_user_points_in_org_by_identifier(db, org, user_identifier):
    """An active member's total and points history in the org."""
    # Student ids and profile fields only go to the org's officers, also while ACCESS_ENFORCE is off
    return service.member_points(db, org, user_identifier, is_org_officer(org))
