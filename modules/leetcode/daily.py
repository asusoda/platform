"""The LeetCode daily post and its solve checks, run as jobs. No Flask and no gateway bot here.

A leetcode_daily row per local date is claimed before posting, so two workers or a restart never
post twice. Members still to verify come from the database on every run, not from bot memory.
"""

import asyncio
import datetime
from collections.abc import Callable
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError

from core import discord_messages
from core.discord_directory import DiscordUnavailable
from core.logging_config import get_logger
from modules.leetcode import client, service
from modules.leetcode.models import LeetCodeDaily

logger = get_logger("leetcode.daily")

DIFFICULTY_COLORS = {"Easy": 0x00B8A3, "Medium": 0xFFC01E, "Hard": 0xFF375F}
CHECK_MARK = "✅"


def question_embed(question: dict, is_daily: bool = False) -> dict:
    """The Discord embed for a question, as the API's JSON."""
    # Topics give away the intended approach, so they sit behind a spoiler
    tags = " ".join(f"`{t['name']}`" for t in question.get("topicTags", []))
    title_prefix = "\U0001f4c5 Daily Challenge" if is_daily else "\U0001f3b2 Random Problem"
    embed: dict[str, Any] = {
        "title": f"{title_prefix} — {question['title']}",
        "url": f"https://leetcode.com/problems/{question['titleSlug']}/",
        "color": DIFFICULTY_COLORS.get(question.get("difficulty", ""), 0x5865F2),
        "fields": [
            {"name": "Difficulty", "value": question.get("difficulty", "Unknown"), "inline": True},
            {"name": "Acceptance", "value": f"{question.get('acRate', 0):.1f}%", "inline": True},
            {"name": "ID", "value": f"#{question.get('frontendQuestionId', '?')}", "inline": True},
            {"name": "Topics", "value": f"||{tags}||" if tags else "None", "inline": False},
        ],
        "footer": {"text": "Good luck! Link your account with /link to get auto-verified."},
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    if question.get("paidOnly"):
        embed["description"] = "⚠️ This is a **premium** problem (LeetCode Plus required)."
    return embed


def _config():
    from shared import config

    return config


def _int(value: str | None, name: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("%s is not a number: %r", name, value)
        return None


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(_config().TIMEZONE)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone %r, using UTC", _config().TIMEZONE)
        return ZoneInfo("UTC")


def _post_time() -> datetime.time:
    try:
        hour, minute = (int(x) for x in str(_config().LEETCODE_DAILY_TIME).split(":")[:2])
        return datetime.time(hour, minute)
    except ValueError:
        logger.warning("LEETCODE_DAILY_TIME %r is not HH:MM, using 09:00", _config().LEETCODE_DAILY_TIME)
        return datetime.time(9, 0)


def post_daily(
    db,
    now: datetime.datetime | None = None,
    fetch: Callable[[], dict] | None = None,
    send: Callable[..., dict] = discord_messages.send_message,
    react: Callable[..., None] = discord_messages.add_reaction,
) -> dict:
    """Post today's question once, at or after LEETCODE_DAILY_TIME in TIMEZONE. Commits."""
    channel_id = _int(_config().LEETCODE_CHANNEL_ID, "LEETCODE_CHANNEL_ID")
    if channel_id is None:
        return {"posted": False, "reason": "LEETCODE_CHANNEL_ID is not set"}
    local = (now or datetime.datetime.now(datetime.UTC)).astimezone(_zone())
    if local.time() < _post_time():
        return {"posted": False, "reason": "not yet"}
    today = local.date()
    if db.get(LeetCodeDaily, today) is not None:
        return {"posted": False, "reason": "already posted"}

    question = fetch() if fetch else asyncio.run(client.fetch_daily_question())
    db.add(LeetCodeDaily(post_date=today, title_slug=question["titleSlug"], channel_id=str(channel_id)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"posted": False, "reason": "already posted"}

    role = _int(_config().LEETCODE_ROLE_PING, "LEETCODE_ROLE_PING")
    payload = {"content": f"<@&{role}>" if role else None, "embeds": [question_embed(question, is_daily=True)]}
    try:
        message = send(_config().BOT_TOKEN, channel_id, payload)
    except DiscordUnavailable:
        # Give the day back so the next run tries again
        db.query(LeetCodeDaily).filter_by(post_date=today).delete()
        db.commit()
        raise
    row = db.get(LeetCodeDaily, today)
    row.message_id = str(message["id"])
    db.commit()
    try:
        react(_config().BOT_TOKEN, channel_id, message["id"], CHECK_MARK)
    except DiscordUnavailable:
        logger.warning("Could not react to the daily post", exc_info=True)
    logger.info("Posted daily LeetCode %s", question["titleSlug"])
    return {"posted": True, "slug": question["titleSlug"]}


def _solved_on(submissions: list[dict], slug: str, day: datetime.date, zone: ZoneInfo) -> bool:
    for sub in submissions:
        if sub.get("titleSlug") != slug:
            continue
        try:
            ts = int(sub.get("timestamp"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if datetime.datetime.fromtimestamp(ts, tz=zone).date() == day:
            return True
    return False


def verify(
    db,
    now: datetime.datetime | None = None,
    submissions: Callable[[str], list[dict]] | None = None,
    send: Callable[..., dict] = discord_messages.send_message,
) -> dict:
    """Check today's linked members who have not solved yet, record solves, reply under the post. Commits."""
    zone = _zone()
    today = (now or datetime.datetime.now(datetime.UTC)).astimezone(zone).date()
    post = db.get(LeetCodeDaily, today)
    if post is None or post.message_id is None:
        return {"checked": 0, "verified": 0}
    pending = service.unsolved_links(db, today)
    verified = 0
    for discord_id, username in pending.items():
        try:
            found = submissions(username) if submissions else asyncio.run(client.fetch_recent_ac_submissions(username))
        except RuntimeError:
            logger.warning("Could not read submissions of %s", username, exc_info=True)
            continue
        if not _solved_on(found, str(post.title_slug), today, zone):
            continue
        service.record_solve(db, discord_id, str(post.title_slug), today)
        verified += 1
        try:
            send(
                _config().BOT_TOKEN,
                post.channel_id,
                {
                    "content": f"{CHECK_MARK} <@{discord_id}> solved today's challenge as **{username}**!",
                    "message_reference": {"message_id": post.message_id, "fail_if_not_exists": False},
                    "allowed_mentions": {"users": [discord_id]},
                },
            )
        except DiscordUnavailable:
            logger.warning("Could not announce the solve of %s", discord_id, exc_info=True)
    return {"checked": len(pending), "verified": verified}
