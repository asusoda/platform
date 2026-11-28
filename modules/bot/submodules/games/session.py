"""GameSession: the Jeopardy game of one org in its Discord server, with its channels, roles and messages.

Each change writes the org's active_game row. GameSession.restore builds the session again from that row.
"""

import random
from dataclasses import dataclass, field
from typing import Any

import discord
from sqlalchemy.exc import SQLAlchemyError

from core.db import db_connect
from core.log import get_logger
from modules.bot.submodules.games import service
from modules.bot.submodules.games.jeopardy.game import JeopardyGame
from modules.bot.submodules.games.ui import QuestionPost

logger = get_logger(__name__)

SIGNUP_EMOJI = "✅"


def server_name(guild: discord.Guild) -> str:
    """The name of the organization on this Discord server, or the server's own name."""
    from modules.organizations.service import name_for_guild

    db = db_connect.SessionLocal()
    try:
        return name_for_guild(db, guild.id) or guild.name
    except SQLAlchemyError:
        return guild.name
    finally:
        db.close()


def _id(item: Any) -> str | None:
    return str(item.id) if item is not None else None


def _ids(items: list) -> list[str | None]:
    return [_id(item) for item in items]


@dataclass
class GameSession:
    """The game of one org. org_id and guild say whose game it is; the rest is the game and its Discord objects."""

    org_id: int
    guild: discord.Guild
    game: JeopardyGame
    date: str | None = None
    time: str | None = None
    category: discord.CategoryChannel | None = None
    stage: discord.StageChannel | None = None
    roles: list[discord.Role] = field(default_factory=list)
    voice_channels: list[discord.VoiceChannel] = field(default_factory=list)
    announcement_channel: discord.TextChannel | None = None
    scoreboard_channel: discord.TextChannel | None = None
    signup: discord.Message | None = None
    scoreboard: discord.Message | None = None
    gameboard: discord.Message | None = None
    # Question uuid -> {"message": the question post, "roles_answered": the team roles that buzzed in}
    question_post: dict[str, dict] = field(default_factory=dict)

    def is_setup(self) -> bool:
        return self.game.is_announced

    def helper_data(self) -> dict:
        """The Discord ids of the session, as stored in active_game.helper_data."""
        return {
            "date": self.date,
            "time": self.time,
            "category": _id(self.category),
            "stage": _id(self.stage),
            "roles": _ids(self.roles),
            "voice_channels": _ids(self.voice_channels),
            "announcement_channel": _id(self.announcement_channel),
            "scoreboard_channel": _id(self.scoreboard_channel),
            "signup_message": _id(self.signup),
            "scoreboard_message": _id(self.scoreboard),
            "gameboard_message": _id(self.gameboard),
            "question_posts": {
                uuid: {"message": _id(post["message"]), "roles_answered": _ids(post["roles_answered"])}
                for uuid, post in self.question_post.items()
            },
            "players": _ids(self.game.players),
            "teams": {team.name: _ids(team.members) for team in self.game.teams},
        }

    def save(self) -> None:
        """Write the active_game row of the org."""
        db = db_connect.SessionLocal()
        try:
            service.save_state(db, self.org_id, self.guild.id, self.game.to_json(), self.helper_data())
        finally:
            db.close()
        logger.debug("game state saved org_id=%s guild_id=%s game=%s", self.org_id, self.guild.id, self.game.name)

    def forget(self) -> None:
        """Delete the active_game row of the org."""
        db = db_connect.SessionLocal()
        try:
            service.clear_state(db, self.org_id)
        finally:
            db.close()

    async def setup(self) -> discord.Message:
        """Make the category, stage, team roles and voice channels and the announcement. Returns the sign-up post."""
        guild = self.guild
        self.category = await guild.create_category("Jeopardy")
        self.save()
        await self.category.edit(position=0)
        self.stage = await guild.create_stage_channel(name="Game Stage", topic=self.game.name, category=self.category)
        self.save()
        for team in self.game.teams:
            role = await guild.create_role(name=team.get_name())
            self.roles.append(role)
            overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False, speak=False),
                role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
            }
            channel = await guild.create_voice_channel(team.get_name(), overwrites=overwrites, category=self.category)
            self.voice_channels.append(channel)
            self.save()

        self.announcement_channel = await guild.create_text_channel("announcements", category=self.category)
        self.game.is_announced = True
        embed = discord.Embed(
            title="🌟 JEOPARDY GAME NIGHT ANNOUNCEMENT 🌟",
            description="Get ready for an exciting evening of trivia and fun!",
            color=discord.Color.random(),
        )
        embed.add_field(name="Date", value=self.date or "TBD", inline=False)
        embed.add_field(name="Time", value=self.time or "TBD", inline=False)
        embed.add_field(name="Location", value=f"The {server_name(guild)} Discord Server", inline=False)
        embed.add_field(name="How to Enroll?", value=f"React with {SIGNUP_EMOJI}.", inline=False)
        embed.set_footer(text=f"React with {SIGNUP_EMOJI} to enroll!")
        self.signup = await self.announcement_channel.send(embed=embed)
        self.save()
        await self.signup.add_reaction(SIGNUP_EMOJI)
        return self.signup

    async def clear(self) -> None:
        """Delete the game's roles and channels from the Discord server. A deleted object is skipped."""
        channels = [*self.voice_channels, self.announcement_channel, self.scoreboard_channel, self.stage, self.category]
        for item in [*self.roles, *channels]:
            if item is None:
                continue
            try:
                await item.delete()
            except discord.NotFound:
                logger.info("game object already deleted org_id=%s id=%s", self.org_id, item.id)

    def add_member(self, member: discord.Member | discord.User) -> None:
        self.game.add_member(member)
        self.save()

    def remove_member(self, member: discord.Member | discord.User) -> bool:
        removed = self.game.remove_member(member)
        if removed:
            self.save()
        return removed

    async def start(self) -> bool:
        """Start the game. False when setup did not run or the game runs."""
        if not self.game.is_announced or self.game.is_started:
            return False
        self.game.start()
        self.scoreboard_channel = await self.guild.create_text_channel("scoreboard", category=self.category)
        self.game.attach_roles(self.roles)
        self.balance_teams()
        self.save()
        await self.assign_roles()
        await self.update_scoreboard()
        await self.update_gameboard()
        return True

    def balance_teams(self) -> None:
        """Put each player in one team. Team sizes differ by one at most."""
        members = list(self.game.get_members())
        random.shuffle(members)
        team_count = len(self.game.teams)
        if team_count == 0:
            raise ValueError("No teams are set up in the game.")
        for team in self.game.teams:
            team.members.clear()
        for i, member in enumerate(members):
            self.game.teams[i % team_count].members.append(member)

    async def assign_roles(self) -> None:
        for team in self.game.teams:
            if team.role is None:
                continue
            for member in team.members:
                # Only a server member can get a role
                if isinstance(member, discord.Member):
                    await member.add_roles(team.role)

    def _question_embed(self, uuid: str, description: str, answer: bool = False) -> discord.Embed | None:
        question = self.game.get_question_by_uuid(uuid)
        if question is None:
            return None
        title = "🌟ANSWER🌟" if answer else "🌟QUESTION🌟"
        embed = discord.Embed(title=title, description=description, color=discord.Color.random())
        embed.add_field(name="Category", value=question.category, inline=True)
        embed.add_field(name="Value", value=question.value, inline=True)
        embed.add_field(name="Question", value=question.question, inline=False)
        if answer:
            embed.add_field(name="Answer", value=question.answer, inline=False)
        return embed

    def _view(self, uuid: str) -> QuestionPost | None:
        question = self.game.get_question_by_uuid(uuid)
        if question is None or self.stage is None:
            return None
        post = self.question_post.get(uuid)
        avoid = post["roles_answered"] if post else []
        return QuestionPost(question=question, voice=self.stage, session=self, question_uuid=uuid, avoid=avoid)

    async def show_question(self, uuid: str) -> bool:
        """Post the question, or post it again when it was posted. False when there is no such question."""
        if self.announcement_channel is None:
            return False
        post = self.question_post.get(uuid)
        embed = self._question_embed(uuid, "Here is the question again! \n" if post else "Here is the question! \n")
        view = self._view(uuid)
        if embed is None or view is None:
            return False
        if post is not None and post["message"] is not None:
            await post["message"].edit(embed=embed, view=view)
            return True
        message = await self.announcement_channel.send(embed=embed, view=view)
        self.question_post[uuid] = {"message": message, "roles_answered": post["roles_answered"] if post else []}
        self.save()
        await self.update_gameboard()
        return True

    async def show_answer(self, uuid: str) -> bool:
        """Mark the question answered and post its answer. False when there is no such question."""
        if self.announcement_channel is None:
            return False
        answered, _question = self.game.answer_question(uuid)
        embed = self._question_embed(uuid, "Here is the answer! \n", answer=True)
        if not answered or embed is None:
            return False
        self.save()
        await self.announcement_channel.send(embed=embed)
        return True

    async def award_points(self, team_name: str, points: int) -> bool:
        """False when no team has that name."""
        if not self.game.award_points(team_name, points):
            return False
        self.save()
        await self.update_scoreboard()
        return True

    async def update_scoreboard(self) -> None:
        if self.scoreboard_channel is None or not self.game.is_started:
            return
        embed = discord.Embed(
            title="🌟SCOREBOARD🌟", description="Here is the scoreboard! \n", color=discord.Color.blurple()
        )
        for team in self.game.teams:
            embed.add_field(name=team.name, value=str(team.score), inline=True)
        if self.scoreboard is None:
            self.scoreboard = await self.scoreboard_channel.send(embed=embed)
            self.save()
        else:
            await self.scoreboard.edit(embed=embed)

    async def update_gameboard(self) -> None:
        if self.announcement_channel is None or not self.game.is_started:
            return
        embed = discord.Embed(
            title=f"Jeopardy Game: {self.game.name}", description=self.game.description, color=0x1E90FF
        )
        for category, values in self.game.get_board().items():
            embed.add_field(name=category, value=str(values), inline=False)
        if self.gameboard is None:
            self.gameboard = await self.announcement_channel.send(embed=embed)
            self.save()
        else:
            await self.gameboard.edit(embed=embed)

    async def end(self) -> bool:
        """Post the winners. False when setup did not run."""
        if self.announcement_channel is None:
            return False
        embed = discord.Embed(title="🌟GAME OVER🌟", description="Thanks for playing! \n", color=discord.Color.green())
        winners = self.game.get_winners()
        embed.add_field(
            name="Winner" if len(winners) == 1 else "Winners", value=", ".join(winners) or "No players", inline=False
        )
        await self.announcement_channel.send(embed=embed)
        return True

    def get_member_role(self, member) -> discord.Role | None:
        """The team role of the member, or None."""
        for role in self.roles:
            if role in member.roles:
                return role
        return None

    @classmethod
    async def restore(cls, guild: discord.Guild, org_id: int, game_data: dict, helper: dict) -> "GameSession":
        """The session that an active_game row holds. A channel, role, message or member that is gone is dropped."""
        session = cls(org_id=org_id, guild=guild, game=JeopardyGame.from_json(game_data))
        session.date, session.time = helper.get("date"), helper.get("time")
        dropped: list[str] = []

        def channel(key: str):
            found = _lookup(guild.get_channel, helper.get(key))
            if helper.get(key) and found is None:
                dropped.append(f"{key}={helper.get(key)}")
            return found

        def each(getter, key: str) -> list:
            found = []
            for item_id in helper.get(key) or []:
                item = _lookup(getter, item_id)
                if item is None:
                    dropped.append(f"{key}={item_id}")
                else:
                    found.append(item)
            return found

        async def message(source, key: str, message_id: str | None = None):
            message_id = message_id or helper.get(key)
            if not message_id:
                return None
            if source is not None:
                try:
                    return await source.fetch_message(int(message_id))
                except discord.HTTPException:
                    pass
            dropped.append(f"{key}={message_id}")
            return None

        session.category = channel("category")
        session.stage = channel("stage")
        session.announcement_channel = channel("announcement_channel")
        session.scoreboard_channel = channel("scoreboard_channel")
        session.roles = each(guild.get_role, "roles")
        session.voice_channels = each(guild.get_channel, "voice_channels")
        players = {str(member.id): member for member in each(guild.get_member, "players")}
        session.game.players = list(players.values())
        for team in session.game.teams:
            team.members = [players[i] for i in (helper.get("teams") or {}).get(team.name, []) if i in players]
        if session.game.is_started:
            session.game.attach_roles(session.roles)
        announcements = session.announcement_channel
        session.signup = await message(announcements, "signup_message")
        session.scoreboard = await message(session.scoreboard_channel, "scoreboard_message")
        session.gameboard = await message(announcements, "gameboard_message")
        for uuid, post in (helper.get("question_posts") or {}).items():
            found = await message(announcements, "question_post", post.get("message"))
            answered = []
            for role_id in post.get("roles_answered") or []:
                # None is a player who buzzed in with no team role
                role = _lookup(guild.get_role, role_id)
                if role_id is not None and role is None:
                    dropped.append(f"roles_answered={role_id}")
                else:
                    answered.append(role)
            session.question_post[uuid] = {"message": found, "roles_answered": answered}
        if dropped:
            logger.warning(
                "game restore dropped missing Discord objects org_id=%s guild_id=%s %s",
                org_id,
                guild.id,
                " ".join(dropped),
            )
        return session

    async def reattach_views(self) -> None:
        """Put a new buzz-in view on each question post that is not answered, so its button works again."""
        for uuid, post in self.question_post.items():
            question = self.game.get_question_by_uuid(uuid)
            view = self._view(uuid)
            if post["message"] is None or question is None or question.answered or view is None:
                continue
            try:
                await post["message"].edit(view=view)
            except discord.HTTPException:
                logger.warning("question view not restored org_id=%s question=%s", self.org_id, uuid, exc_info=True)


def _lookup(getter, item_id: str | None):
    """getter(int(item_id)), or None when item_id is empty."""
    return getter(int(item_id)) if item_id else None
