"""Points logic shared by the REST API, tools and jobs. No Flask here."""

from sqlalchemy import and_, func

from modules.auth import scopes
from modules.points.models import Points, User, UserOrganizationMembership

scopes.declare("points:read", "Read the org's points leaderboard (names and totals, no emails or ASU IDs)")


def leaderboard(db, org, limit: int = 10) -> list[dict]:
    """Active members ranked by total points in this org. Names and totals only."""
    rows = (
        db.query(User.name, func.coalesce(func.sum(Points.points), 0).label("total_points"))
        .join(UserOrganizationMembership, User.id == UserOrganizationMembership.user_id)
        .outerjoin(Points, and_(Points.user_id == User.id, Points.organization_id == org.id))
        .filter(UserOrganizationMembership.organization_id == org.id)
        .filter(UserOrganizationMembership.is_active)
        .group_by(User.id, User.name)
        .order_by(func.coalesce(func.sum(Points.points), 0).desc(), User.name.asc())
        .limit(limit)
        .all()
    )
    return [{"rank": i + 1, "name": name, "total_points": float(total)} for i, (name, total) in enumerate(rows)]
