"""The LeetCode daily post and solve checks."""

from core.jobs import job


@job("leetcode.post_daily", cron="*/5 * * * *", audit=False)
def post_daily() -> None:
    """Post today's question once LEETCODE_DAILY_TIME has passed."""
    from modules.leetcode import daily
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        daily.post_daily(db)
    finally:
        db.close()


@job("leetcode.verify", cron="*/10 * * * *", audit=False)
def verify() -> None:
    """Record today's solves of linked members and announce them under the post."""
    from modules.leetcode import daily
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        daily.verify(db)
    finally:
        db.close()
