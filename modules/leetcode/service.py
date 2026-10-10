"""LeetCode links, solves and stats. Used by the Discord cog; no Flask here."""

import datetime

from sqlalchemy import func

from core.logging_config import get_logger
from modules.leetcode.models import LeetCodeLink, LeetCodeSolve

logger = get_logger("leetcode.service")


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
