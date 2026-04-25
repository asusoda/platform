from sqlalchemy import JSON, Column, Date, DateTime, Integer, String, UniqueConstraint, func

from modules.utils.base import Base


class JeopardyGame(Base):
    __tablename__ = "jeopardy_game"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    data = Column(JSON)


class ActiveGame(Base):
    __tablename__ = "active_game"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    game_data = Column(JSON)
    helper_data = Column(JSON)


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
