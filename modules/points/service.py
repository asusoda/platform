"""Points logic shared by the REST API, tools and jobs. No Flask here."""

from typing import cast

from sqlalchemy import func

from core.errors import ServiceError
from modules.auth import scopes
from modules.members import service as users
from modules.members.models import User, UserOrganizationMembership
from modules.organizations.models import Organization
from modules.points.models import Points

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
