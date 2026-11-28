"""Points logic shared by the REST API, tools and jobs. No Flask here."""

from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import func

from core.errors import ServiceError
from core.log import get_logger
from modules.auth import scopes
from modules.members import service as users
from modules.members.models import User, UserOrganizationMembership
from modules.organizations.models import Organization
from modules.points.models import Points

logger = get_logger(__name__)

scopes.declare("points:read", "Read the org's points leaderboard (names and totals, no emails or student IDs)")
scopes.declare("points:write", "Award points, delete point entries and import event attendance CSVs")

MAX_IDS = 100  # members or entries in one award or delete
MAX_ENTRIES = 1000  # entries in one list


class PointsError(ServiceError):
    pass


def total_points(db, user_id, organization_id):
    """The sum of the user's points in the org, or None when there are none."""
    return db.query(func.sum(Points.points)).filter_by(user_id=user_id, organization_id=organization_id).scalar()


def totals_by_user(db, organization_id) -> dict[int, float]:
    """The sum of each user's points in the org, by user id. Users with no entries are not in it. One query."""
    rows = (
        db.query(Points.user_id, func.sum(Points.points))
        .filter(Points.organization_id == organization_id)
        .group_by(Points.user_id)
        .all()
    )
    return dict(rows)


def member_json(user: User, membership: UserOrganizationMembership | None) -> dict:
    """A member with both student id key sets, the org's profile fields, the major and the Discord link."""
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        **users.member_fields(user, membership),
        "major": user.major,
        "discord_linked": bool(user.discord_id),
    }


def member_orgs(db, user_id, current_org_id) -> list[dict]:
    """Each org the user is an active member of, with the user's points there."""
    rows = (
        db.query(Organization)
        .join(UserOrganizationMembership, UserOrganizationMembership.organization_id == Organization.id)
        .filter(UserOrganizationMembership.user_id == user_id, UserOrganizationMembership.is_active.is_(True))
        .order_by(UserOrganizationMembership.id)
        .all()
    )
    return [
        {
            "id": org.id,
            "name": org.name,
            "prefix": org.prefix,
            "description": org.description,
            "points": total_points(db, user_id, org.id) or 0,
            "is_current": org.id == current_org_id,
        }
        for org in rows
    ]


def point_json(point: Points) -> dict:
    """A point entry as the officer routes return it."""
    return {
        "id": point.id,
        "points": point.points,
        "event": point.event,
        "awarded_by_officer": point.awarded_by_officer,
        "timestamp": point.timestamp.isoformat() if point.timestamp else None,
        "last_updated": point.last_updated.isoformat() if point.last_updated else None,
        "user_id": point.user_id,
        "organization_id": point.organization_id,
    }


def history_json(point: Points) -> dict:
    """A point entry in a member's points history."""
    return {
        "id": point.id,
        "points": point.points,
        "event": point.event,
        "awarded_by_officer": point.awarded_by_officer,
        "timestamp": point.timestamp.isoformat() if point.timestamp else None,
        "last_updated": point.last_updated.isoformat() if point.last_updated else None,
    }


def add_entry(db, organization_id, user: User, points, event, awarded_by) -> Points:
    """Add one point entry for the user in the org. Commits."""
    point = Points(
        points=points, user_id=user.id, organization_id=organization_id, event=event, awarded_by_officer=awarded_by
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return point


def delete_event_entry(db, organization_id, user_email, event) -> Points:
    """Delete the first entry of the user with this email for this event in the org. Commits."""
    user = db.query(User).filter_by(email=user_email).first()
    if not user:
        raise PointsError("User not found", 404)
    entry = db.query(Points).filter_by(user_id=user.id, organization_id=organization_id, event=event).first()
    if not entry:
        raise PointsError("Points entry not found", 404)
    db.delete(entry)
    db.commit()
    return entry


def delete_entry(db, organization_id, entry_id: int) -> dict:
    """Delete the point entry with this id in the org and return it. Commits."""
    entry = db.query(Points).filter_by(id=entry_id, organization_id=organization_id).first()
    if entry is None:
        raise PointsError("Points entry not found", 404)
    deleted = point_json(entry)
    db.delete(entry)
    db.commit()
    return deleted


def members_with_points(db, organization_id) -> list[dict]:
    """The org's active members with their contact fields and total points, in membership order."""
    totals = totals_by_user(db, organization_id)
    return [
        {
            "id": user.id,
            "uuid": user.uuid,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            **users.legacy_member_fields(user),
            "major": user.major,
            "discord_linked": bool(user.discord_id),
            "points": totals.get(user.id) or 0,
            "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for membership, user in users.active_members(db, organization_id)
    ]


def entries(db, organization_id, event: str | None = None, limit: int = MAX_ENTRIES) -> list[dict]:
    """The org's point entries, newest first. event keeps the entries of one event."""
    query = db.query(Points).filter_by(organization_id=organization_id)
    if event is not None:
        query = query.filter_by(event=event)
    return [point_json(point) for point in query.order_by(Points.id.desc()).limit(limit).all()]


def member(db, organization_id, key: str) -> User:
    """The active member whose email, uuid, username or Discord id is key."""
    user = users.find_by_identifier(db, key)
    if user is None and key.isdigit():
        user = db.query(User).filter_by(discord_id=key).first()
    if user is None or users.active_membership(db, user.id, organization_id) is None:
        raise PointsError(f"No member of this org is {key}", 404)
    return user


def member_history(db, organization_id, key: str) -> dict:
    """One member's total and point entries in the org, last updated first."""
    user = member(db, organization_id, key)
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email, "username": user.username},
        "total_points": total_points(db, user.id, organization_id) or 0,
        "points_history": [history_json(record) for record in history(db, user.id, organization_id)],
    }


def award(db, organization_id, members: list[str], points: float, event: str | None, awarded_by: str) -> list[dict]:
    """Give each member the same points in one commit. If one key is not a member, nothing changes."""
    found: dict[str, User] = {}
    missing = []
    for key in members:
        try:
            found[key] = member(db, organization_id, key)
        except PointsError:
            missing.append(key)
    if missing:
        raise PointsError(f"Not members of this org: {', '.join(missing)}", 404)
    rows = [
        Points(
            points=points, user_id=user.id, organization_id=organization_id, event=event, awarded_by_officer=awarded_by
        )
        for user in found.values()
    ]
    db.add_all(rows)
    db.commit()
    return [point_json(row) for row in rows]


def _matching(db, organization_id, ids: list[int] | None, event: str | None) -> list[Points]:
    if not ids and event is None:
        raise PointsError("Send ids or event")
    query = db.query(Points).filter_by(organization_id=organization_id)
    if ids:
        query = query.filter(Points.id.in_(ids))
    if event is not None:
        query = query.filter_by(event=event)
    rows = query.order_by(Points.id).all()
    missing = sorted(set(ids or []) - {cast(int, row.id) for row in rows})
    if missing:
        raise PointsError(f"No point entries with ids {', '.join(str(i) for i in missing)}", 404)
    if not rows:
        raise PointsError("No point entries match", 404)
    return rows


def delete_entries(db, organization_id, ids: list[int] | None = None, event: str | None = None) -> dict:
    """Delete point entries by id, or every entry of an event, in one commit."""
    rows = _matching(db, organization_id, ids, event)
    deleted = [row.id for row in rows]
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": deleted}


def delete_preview(db, organization_id, ids: list[int] | None = None, event: str | None = None) -> dict:
    """The entries that delete_entries would delete. Changes nothing."""
    rows = _matching(db, organization_id, ids, event)
    return {
        "count": len(rows),
        "points": sum(cast(float, row.points) or 0.0 for row in rows),
        "ids": [row.id for row in rows],
    }


def history(db, user_id, organization_id) -> list[Points]:
    """The user's point entries in the org, last updated first."""
    return (
        db.query(Points)
        .filter_by(user_id=user_id, organization_id=organization_id)
        .order_by(Points.last_updated.desc())
        .all()
    )


def all_entries(db, organization_id) -> list[dict]:
    """Every point entry of the org, oldest first."""
    rows = db.query(Points).filter_by(organization_id=organization_id).order_by(Points.id).all()
    return [point_json(point) for point in rows]


def _org_json(organization: Organization) -> dict:
    return {"name": organization.name, "prefix": organization.prefix}


def save_member(db, organization: Organization, data: Mapping[str, Any]) -> tuple[dict, bool]:
    """Create, update or link a member of the org for an officer. Returns (body, created). Commits.

    A missing field keeps the stored value. Raises PointsError 400 when the member is refused.
    """
    fields = users.member_input(data)
    user_data = {
        key: fields.get(key)
        for key in ("username", "email", "name", "student_id", "class_standing", "major", "profile_fields")
    }
    user_data = {key: value for key, value in user_data.items() if value is not None}
    user, ok, message = users.manage_user_in_organization(
        db, organization.id, user_data, data.get("discord_id"), data.get("user_identifier"), by_officer=True
    )
    if not ok or user is None:
        raise PointsError(message)
    membership = (
        db.query(UserOrganizationMembership).filter_by(user_id=user.id, organization_id=organization.id).first()
    )
    body = {
        "message": message,
        "user": {
            **member_json(user, membership),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "organization": _org_json(organization),
    }
    return body, "created" in message


def add_points(db, organization_id, data: Mapping[str, Any], awarded_by) -> dict:
    """Add points to the user with this Discord id, else this email, uuid or username. Commits."""
    discord_id = data.get("user_discord_id")
    user_identifier = data.get("user_identifier")
    if not discord_id and not user_identifier:
        raise PointsError("Either 'user_discord_id' or 'user_identifier' must be provided")
    if "points" not in data:
        raise PointsError("points is required")
    user = db.query(User).filter_by(discord_id=discord_id).first() if discord_id else None
    if not user and user_identifier:
        user = users.find_by_identifier(db, user_identifier)
    if not user:
        raise PointsError("User does not exist", 404)
    return point_json(add_entry(db, organization_id, user, data["points"], data.get("event"), awarded_by))


def _points_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise PointsError("points must be a number") from None


def assign(db, organization: Organization, data: Mapping[str, Any], awarded_by) -> dict:
    """Add points to an active member of the org found by email, uuid or username. Commits."""
    if not data.get("user_identifier"):
        raise PointsError("user_identifier is required")
    if not data.get("points"):
        raise PointsError("points is required")
    points = _points_value(data["points"])
    user = users.find_by_identifier(db, data["user_identifier"])
    if not user:
        raise PointsError("User not found", 404)
    if not users.active_membership(db, user.id, organization.id):
        raise PointsError("User is not a member of this organization")
    point = add_entry(db, organization.id, user, points, data.get("event"), awarded_by)
    return {
        "message": "Points assigned successfully",
        "points": point_json(point),
        "user": {"name": user.name, "email": user.email},
        "organization": _org_json(organization),
    }


def delete_event_points(db, organization_id, data: Mapping[str, Any]) -> dict:
    """Delete a member's first entry for an event, by the member's email. Commits."""
    if "user_email" not in data or "event" not in data:
        raise PointsError("user_email and event are required")
    entry = delete_event_entry(db, organization_id, data["user_email"], data["event"])
    return {
        "message": "Points deleted successfully",
        "deleted_points": {
            "points": entry.points,
            "event": entry.event,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            "awarded_by_officer": entry.awarded_by_officer,
            "user_id": entry.user_id,
            "organization_id": entry.organization_id,
        },
    }


def update_member_fields(db, organization_id, user_identifier: str, data: Mapping[str, Any]) -> dict:
    """Update the fields sent for an active member. Commits.

    The body has "details" when a field failed. Raises MemberError when the member is not found.
    """
    result = users.update_member(db, organization_id, user_identifier, data)
    updated_fields, errors = result["updated_fields"], result["errors"]
    if errors:
        return {"error": "Some fields failed to update", "details": errors}
    if not updated_fields:
        return {"message": "No fields to update"}
    return {
        "message": f"Updated fields: {', '.join(updated_fields)}",
        "updated_fields": updated_fields,
        "user": member_json(result["user"], result["membership"]),
    }


def member_points(db, organization: Organization, user_identifier: str, show_details: bool) -> dict:
    """An active member's total and points history. show_details adds student ids, profile fields and the major."""
    user = users.find_by_identifier(db, user_identifier)
    if not user:
        raise PointsError("User not found", 404)
    membership = users.active_membership(db, user.id, organization.id)
    if not membership:
        raise PointsError("User is not a member of this organization")
    details = {**users.member_fields(user, membership), "major": user.major} if show_details else {}
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email, "username": user.username, **details},
        "organization": _org_json(organization),
        "total_points": total_points(db, user.id, organization.id) or 0,
        "points_history": [history_json(r) for r in history(db, user.id, organization.id)],
    }


def member_login(db, organization: Organization, data: Mapping[str, Any], discord_id) -> dict:
    """Link or create the member that signs in to the store. Commits. Raises PointsError 500 when it fails."""
    fields = users.member_input(data)
    user_data = {key: fields.get(key) for key in ("name", "username", "email", "student_id", "class_standing", "major")}
    user, ok, message = users.manage_user_in_organization(db, organization.id, user_data, discord_id=discord_id)
    if not ok or user is None:
        logger.warning("member login refused org=%s: %s", organization.prefix, message)
        raise PointsError("Failed to create or link user account", 500)
    return {
        "message": "Login successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            "asu_id": user.student_id,
            "discord_linked": bool(user.discord_id),
        },
        "organization": {"id": organization.id, **_org_json(organization)},
    }


def member_profile(db, organization: Organization, discord_id, member_user_id, directory) -> dict:
    """The signed-in member's profile, orgs and points. A Discord id comes first and must be in the org's server."""
    if discord_id:
        if directory is None or not directory.is_ready():
            raise PointsError("Discord bot not available", 503)
        if not directory.check_user_membership(int(discord_id), int(organization.guild_id)):
            raise PointsError("You must be a member of this organization to access this resource", 403)
        user = db.query(User).filter_by(discord_id=str(discord_id)).first()
    else:
        user = db.query(User).filter_by(id=member_user_id).first()
    if not user:
        raise PointsError("User not found", 404)
    membership = users.active_membership(db, user.id, organization.id)
    orgs = member_orgs(db, user.id, organization.id)
    current_points = next((o["points"] for o in orgs if o["is_current"]), 0)
    return {
        "user": {
            **member_json(user, membership),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "current_organization": {
            "id": organization.id,
            "name": organization.name,
            "prefix": organization.prefix,
            "points": current_points,
        },
        "organizations": orgs,
        "total_points_all_orgs": sum(o["points"] for o in orgs),
    }
