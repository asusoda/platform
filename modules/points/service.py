"""Points logic shared by the REST API, tools and jobs. No Flask here."""

from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import and_, func

from modules.auth import scopes
from modules.points.models import Points, User, UserOrganizationMembership

scopes.declare("points:read", "Read the org's points leaderboard (names and totals, no emails or student IDs)")

# Request and response keys kept for thesoda.io and web/, and the column each one names
LEGACY_MEMBER_KEYS = {"asu_id": "student_id", "academic_standing": "class_standing"}


def member_input(data: Mapping[str, Any]) -> dict[str, Any]:
    """Request fields with each legacy key renamed to its column. A column name sent as well wins."""
    fields = {key: value for key, value in data.items() if key not in LEGACY_MEMBER_KEYS}
    for legacy, column in LEGACY_MEMBER_KEYS.items():
        if legacy in data and column not in data:
            fields[column] = data[legacy]
    return fields


def legacy_member_fields(user: User) -> dict[str, Any]:
    """The student id and class standing under their legacy response keys."""
    return {legacy: getattr(user, column) for legacy, column in LEGACY_MEMBER_KEYS.items()}


def member_fields(user: User, membership: UserOrganizationMembership | None = None) -> dict[str, Any]:
    """The student id and class standing under both key sets, and the org's profile fields when a membership is given."""
    fields = legacy_member_fields(user)
    fields.update({column: getattr(user, column) for column in LEGACY_MEMBER_KEYS.values()})
    if membership is not None:
        fields["profile_fields"] = dict(cast(dict[str, Any], membership.profile_fields or {}))
    return fields


def merge_profile_fields(membership: UserOrganizationMembership, changes: Any) -> str | None:
    """Merges changes into the membership's profile fields; a null value removes the key. Returns an error or None."""
    if not isinstance(changes, Mapping):
        return "profile_fields must be an object"
    merged = dict(cast(dict[str, Any], membership.profile_fields or {}))
    for key, value in changes.items():
        if not isinstance(key, str) or not key.strip():
            return "profile_fields keys must be non-empty strings"
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, str | int | float | bool):
            merged[key] = value
        else:
            return f"profile_fields.{key} must be a string, number or boolean"
    membership.profile_fields = merged
    return None


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
