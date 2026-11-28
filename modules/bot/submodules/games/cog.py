"""GameCog: one Jeopardy GameSession for each Discord server, kept in active_game across restarts."""

import discord
from discord.ext import commands
from sqlalchemy.exc import SQLAlchemyError

from core.db import db_connect
from core.log import get_logger
from modules.bot.bot import BotFork
from modules.bot.submodules.games import service
from modules.bot.submodules.games.jeopardy.game import JeopardyGame
from modules.bot.submodules.games.session import SIGNUP_EMOJI, GameSession

logger = get_logger(__name__)


class GameCog(commands.Cog):
    """The games of the bot. sessions maps a guild id to the game of the org on that server."""

    def __init__(self, bot: BotFork):
        self.bot = bot
        self.sessions: dict[int, GameSession] = {}

    def session(self, guild_id: int) -> GameSession | None:
        return self.sessions.get(guild_id)

    def is_setup(self, guild_id: int) -> bool:
        session = self.sessions.get(guild_id)
        return session is not None and session.is_setup()

    def set_game(
        self, org_id: int, guild: discord.Guild, game: dict, date: str | None, time: str | None
    ) -> GameSession:
        """Make the session of the org with this game. setup_game then puts it in the Discord server."""
        session = GameSession(org_id=org_id, guild=guild, game=JeopardyGame(game), date=date, time=time)
        self.sessions[guild.id] = session
        session.save()
        logger.info("game set org_id=%s guild_id=%s game=%s", org_id, guild.id, session.game.name)
        return session

    def get_game(self, guild_id: int) -> dict | None:
        """The game JSON of the server's session, or None."""
        session = self.sessions.get(guild_id)
        return session.game.to_json() if session is not None else None

    async def setup_game(self, guild_id: int) -> bool:
        """Make the game's channels, roles and announcement. False when the server has no session."""
        session = self.sessions.get(guild_id)
        if session is None:
            return False
        signup = await session.setup()
        self.bot.execute("HelperCog", "add_to_listner", signup, SIGNUP_EMOJI)
        return True

    async def clear_game(self, guild_id: int) -> bool:
        """Delete the server's game from Discord and from active_game. False when the server has no session."""
        session = self.sessions.pop(guild_id, None)
        if session is None:
            return False
        if session.signup is not None:
            self.bot.execute("HelperCog", "remove_from_listner", session.signup, SIGNUP_EMOJI)
        await session.clear()
        session.forget()
        logger.info("game cleared org_id=%s guild_id=%s", session.org_id, guild_id)
        return True

    def add_member(self, guild_id: int, member: discord.Member | discord.User) -> bool:
        session = self.sessions.get(guild_id)
        if session is None:
            return False
        session.add_member(member)
        return True

    def remove_member(self, guild_id: int, member: discord.Member | discord.User) -> bool:
        session = self.sessions.get(guild_id)
        return session is not None and session.remove_member(member)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.restore()

    async def restore(self) -> None:
        """Build a session from each active_game row whose server has none. A server the bot is not in is skipped."""
        db = db_connect.SessionLocal()
        try:
            rows = [(row.organization_id, row.guild_id, row.game_data, row.helper_data) for row in service.states(db)]
        except SQLAlchemyError:
            logger.exception("game restore could not read active_game")
            return
        finally:
            db.close()
        for org_id, guild_id, game_data, helper in rows:
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                logger.warning("game restore skipped org_id=%s guild_id=%s: the bot is not in it", org_id, guild_id)
                continue
            if guild.id in self.sessions:
                continue
            try:
                session = await GameSession.restore(guild, org_id, game_data, helper or {})
            except (KeyError, TypeError, ValueError):
                logger.exception("game restore failed org_id=%s guild_id=%s", org_id, guild_id)
                continue
            self.sessions[guild.id] = session
            session.save()
            if session.signup is not None:
                self.bot.execute("HelperCog", "add_to_listner", session.signup, SIGNUP_EMOJI)
            await session.reattach_views()
            logger.info("game restored org_id=%s guild_id=%s game=%s", org_id, guild.id, session.game.name)
