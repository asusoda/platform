"""LeetCode links, solves and stats. Used by the Discord cog; no Flask here."""

import datetime
import re
from typing import cast

from sqlalchemy import func
from sqlalchemy.orm.attributes import flag_modified

from core.logging_config import get_logger
from modules.leetcode.models import LeetCodeLink, LeetCodeSolve

logger = get_logger("leetcode.service")

SNOWFLAKE = re.compile(r"^[0-9]{5,25}$")
HHMM = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
SETTING_KEYS = ("channel_id", "role_ping", "daily_time")


class SettingsError(ValueError):
    pass


def settings(org) -> dict:
    """The org's daily post settings: channel_id, role_ping, daily_time. Missing values are None."""
    saved = (org.config or {}).get("leetcode") or {}
    return {key: saved.get(key) for key in SETTING_KEYS}


def save_settings(db, org, changes: object) -> dict:
    """Merge changes into the org's daily post settings. null clears a value. Commits."""
    if not isinstance(changes, dict) or not changes:
        raise SettingsError("Send an object with channel_id, role_ping or daily_time")
    for key, value in changes.items():
        if key not in SETTING_KEYS:
            raise SettingsError(f"Unknown setting: {key}")
        if value is None:
            continue
        if not isinstance(value, str):
            raise SettingsError(f"{key} must be a string or null")
        pattern = HHMM if key == "daily_time" else SNOWFLAKE
        if not pattern.match(value):
            raise SettingsError(f"{key} is not valid" + (" (use HH:MM)" if key == "daily_time" else " (Discord id)"))
    config = dict(cast(dict, org.config) or {})
    merged = {**(config.get("leetcode") or {}), **changes}
    config["leetcode"] = {key: value for key, value in merged.items() if value is not None}
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return settings(org)


def linked_discord_ids(db) -> list[str]:
    return [row.discord_id for row in db.query(LeetCodeLink).all()]


def links_for(db, discord_ids: list[str]) -> dict[str, str]:
    """Map of discord_id to LeetCode username for the given members."""
    if not discord_ids:
        return {}
    rows = db.query(LeetCodeLink).filter(LeetCodeLink.discord_id.in_(discord_ids)).all()
    return {row.discord_id: row.leetcode_username for row in rows}


def link(db, discord_id: str, username: str) -> None:
    existing = db.query(LeetCodeLink).filter_by(discord_id=discord_id).first()
    if existing:
        existing.leetcode_username = username
    else:
        db.add(LeetCodeLink(discord_id=discord_id, leetcode_username=username))
    db.commit()


def unlink(db, discord_id: str) -> bool:
    existing = db.query(LeetCodeLink).filter_by(discord_id=discord_id).first()
    if not existing:
        return False
    db.delete(existing)
    db.commit()
    return True


def record_solve(db, discord_id: str, title_slug: str, solved_date: datetime.date) -> None:
    """Record one solve per member per day; a second solve the same day is ignored."""
    try:
        if db.query(LeetCodeSolve).filter_by(discord_id=discord_id, solved_date=solved_date).first():
            return
        db.add(LeetCodeSolve(discord_id=discord_id, title_slug=title_slug, solved_date=solved_date))
        db.commit()
    except Exception:
        logger.error(f"Failed to record solve for {discord_id}", exc_info=True)
        db.rollback()


def unsolved_links(db, day: datetime.date) -> dict[str, str]:
    """Linked members with no solve recorded for day: discord_id to LeetCode username."""
    solved = {row.discord_id for row in db.query(LeetCodeSolve.discord_id).filter_by(solved_date=day)}
    return {row.discord_id: row.leetcode_username for row in db.query(LeetCodeLink) if row.discord_id not in solved}


def leaderboard(db, limit: int = 10) -> list[tuple[str, str, int]]:
    """[(discord_id, leetcode_username, solve_count), ...], most solves first."""
    rows = (
        db.query(
            LeetCodeSolve.discord_id,
            LeetCodeLink.leetcode_username,
            func.count(LeetCodeSolve.id).label("solve_count"),
        )
        .outerjoin(LeetCodeLink, LeetCodeLink.discord_id == LeetCodeSolve.discord_id)
        .group_by(LeetCodeSolve.discord_id, LeetCodeLink.leetcode_username)
        .order_by(func.count(LeetCodeSolve.id).desc())
        .limit(limit)
        .all()
    )
    return [(r[0], r[1] or "(unlinked)", r[2]) for r in rows]


def stats(db) -> dict:
    return {
        "total_linked": db.query(LeetCodeLink).count(),
        "total_solves": db.query(LeetCodeSolve).count(),
        "distinct_solvers": db.query(func.count(func.distinct(LeetCodeSolve.discord_id))).scalar() or 0,
    }
