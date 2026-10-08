"""Points logic shared by the REST API, tools and jobs. No Flask here."""

from datetime import datetime

from sqlalchemy import and_, case, func, or_

from modules.auth import scopes
from modules.points.models import Points
from modules.users.models import User, UserOrganizationMembership

scopes.declare("points:read", "Read the org's points leaderboard (names and totals, no emails or student IDs)")


def total_points(db, user_id, organization_id):
    """The sum of the user's points in the org, or None when there are none."""
    return db.query(func.sum(Points.points)).filter_by(user_id=user_id, organization_id=organization_id).scalar()


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


def history(db, user_id, organization_id) -> list[Points]:
    """The user's point entries in the org, last updated first."""
    return (
        db.query(Points)
        .filter_by(user_id=user_id, organization_id=organization_id)
        .order_by(Points.last_updated.desc())
        .all()
    )


def ranked_members(
    db,
    org,
    *,
    positive_only: bool = False,
    with_non_members: bool = False,
    null_total_last: bool = False,
    limit: int | None = None,
):
    """Rows of (user_id, name, email, uuid, student_id, total_points), highest total first, then by name.

    positive_only counts only positive entries. with_non_members also ranks users who have
    points in the org but no active membership. null_total_last orders by the raw sum, so a
    member with no entries sorts as the database sorts NULL, not as 0.
    """
    points_value = case((Points.points > 0, Points.points), else_=0) if positive_only else Points.points
    total = func.coalesce(func.sum(points_value), 0)
    query = db.query(
        User.id.label("user_id"),
        User.name,
        User.email,
        User.uuid,
        User.student_id,
        total.label("total_points"),
    ).select_from(User)
    points_join = and_(Points.user_id == User.id, Points.organization_id == org.id)
    if with_non_members:
        query = (
            query.outerjoin(Points, points_join)
            .outerjoin(
                UserOrganizationMembership,
                and_(
                    UserOrganizationMembership.user_id == User.id,
                    UserOrganizationMembership.organization_id == org.id,
                    UserOrganizationMembership.is_active,
                ),
            )
            .filter(or_(Points.id.isnot(None), UserOrganizationMembership.id.isnot(None)))
        )
    else:
        query = (
            query.join(UserOrganizationMembership, User.id == UserOrganizationMembership.user_id)
            .outerjoin(Points, points_join)
            .filter(UserOrganizationMembership.organization_id == org.id)
            .filter(UserOrganizationMembership.is_active)
        )
    order_total = func.sum(points_value) if null_total_last else total
    query = query.group_by(User.id, User.name, User.email, User.uuid, User.student_id).order_by(
        order_total.desc(), User.name.asc()
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def leaderboard(db, org, limit: int = 10) -> list[dict]:
    """Active members ranked by total points in this org. Names and totals only."""
    rows = ranked_members(db, org, limit=limit)
    return [{"rank": i + 1, "name": row.name, "total_points": float(row.total_points)} for i, row in enumerate(rows)]


def public_leaderboard(db, org, show_details: bool) -> list[dict]:
    """Active members by total points for the public page. Email and student id only with show_details."""
    entries = []
    for row in ranked_members(db, org, null_total_last=True):
        entry = {"name": row.name, "total_points": float(row.total_points) if row.total_points else 0.0}
        if show_details:
            entry.update({"email": row.email, "asu_id": row.student_id})
        entries.append(entry)
    return entries


def _points_details(db, org, user_ids) -> dict:
    """Each user's entries in the org, newest first, keyed by user id."""
    details_by_user = {user_id: [] for user_id in user_ids}
    if not user_ids:
        return details_by_user
    details = (
        db.query(Points.user_id, Points.event, Points.points, Points.timestamp)
        .filter(Points.organization_id == org.id, Points.user_id.in_(user_ids))
        .order_by(Points.user_id, Points.timestamp.desc())
        .all()
    )
    for user_id, event, points, timestamp in details:
        details_by_user.setdefault(user_id, []).append(
            {
                "event": event,
                "points": float(points) if points is not None else 0,
                "timestamp": timestamp.isoformat() if timestamp else None,
            }
        )
    return details_by_user


def officer_leaderboard(db, org, show_email: bool) -> list[dict]:
    """Members and point earners by positive points, with each entry. Identified by email with show_email, else uuid."""
    rows = ranked_members(db, org, positive_only=True, with_non_members=True)
    details = _points_details(db, org, [row.user_id for row in rows])
    return [
        {
            "name": row.name,
            "identifier": row.email if (show_email and row.email) else row.uuid,
            "total_points": float(row.total_points) if row.total_points is not None else 0,
            "points_details": details.get(row.user_id, []),
        }
        for row in rows
    ]


# The semester that curr_sem_points of the global leaderboard counts
SEMESTER_START = datetime(2025, 1, 1)
SEMESTER_END = datetime(2025, 5, 12)


def global_leaderboard(db) -> list[dict]:
    """Every user by total points across all orgs, with each entry and the points in the semester."""
    in_semester = and_(Points.timestamp >= SEMESTER_START, Points.timestamp <= SEMESTER_END)
    leaderboard = (
        db.query(
            User.name,
            func.coalesce(func.sum(Points.points), 0).label("total_points"),
            User.uuid,
            func.coalesce(func.sum(case((in_semester, Points.points), else_=0)), 0).label("curr_sem_points"),
        )
        .outerjoin(Points)  # keeps users with no points
        .group_by(User.uuid)
        .order_by(func.sum(Points.points).desc(), User.name.asc())
        .all()
    )

    user_details = {}
    for user in db.query(User).all():
        points_details = (
            db.query(Points.event, Points.points, Points.timestamp, Points.awarded_by_officer)
            .filter(Points.user_id == user.id)
            .all()
        )
        user_details[user.uuid] = [
            {
                "event": detail.event,
                "points": detail.points,
                "timestamp": detail.timestamp.isoformat() if detail.timestamp else None,
                "awarded_by": detail.awarded_by_officer,
            }
            for detail in points_details
        ]

    return [
        {
            "name": name,
            "total_points": total_points,
            "points_details": user_details.get(uuid, []),
            "curr_sem_points": curr_sem_points,
        }
        for name, total_points, uuid, curr_sem_points in leaderboard
    ]
