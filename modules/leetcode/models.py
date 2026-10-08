from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint, func

from core.base import Base


class LeetCodeLink(Base):
    __tablename__ = "leetcode_link"

    discord_id = Column(String, primary_key=True)
    leetcode_username = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class LeetCodeSolve(Base):
    __tablename__ = "leetcode_solve"

    id = Column(Integer, primary_key=True)
    discord_id = Column(String, nullable=False, index=True)
    title_slug = Column(String, nullable=False)
    solved_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("discord_id", "solved_date", name="uq_solve_user_date"),)


class LeetCodeDaily(Base):
    """One row per local date and target: each daily post happens once, whichever process gets there first.

    scope is "instance" for the post configured by LEETCODE_CHANNEL_ID, or "org:<id>" for an org's own post.
    """

    __tablename__ = "leetcode_daily"

    post_date = Column(Date, primary_key=True)
    scope = Column(String, primary_key=True, server_default="instance")
    title_slug = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    message_id = Column(String, nullable=True)
    posted_at = Column(DateTime, server_default=func.now())
