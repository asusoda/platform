from sqlalchemy import JSON, Column, Integer, String

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
