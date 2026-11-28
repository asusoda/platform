from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class JeopardyGame(Base):
    """A game an officer uploaded. Each org has its own games, one for each name."""

    __tablename__ = "jeopardy_game"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_jeopardy_game_org_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE", name="fk_jeopardy_game_organization_id")
    )
    name: Mapped[str | None] = mapped_column(String)
    data: Mapped[Any | None] = mapped_column(JSON)


class ActiveGame(Base):
    """The game that is set up in the Discord server of one org.

    game_data is JeopardyGame.to_json(). helper_data holds the Discord ids of the game's channels, roles, messages
    and players, and the date and time of the announcement. GameCog rebuilds the game from this row after a restart.
    """

    __tablename__ = "active_game"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_active_game_organization_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE", name="fk_active_game_organization_id")
    )
    guild_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String)
    game_data: Mapped[Any] = mapped_column(JSON)
    helper_data: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
