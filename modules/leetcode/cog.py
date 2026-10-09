from typing import Annotated

import discord
from discord.ext import commands

from core.log import get_logger
from modules.leetcode import service
from modules.leetcode.client import (
    fetch_daily_question,
    fetch_random_question,
    fetch_recent_ac_submissions,
)
from modules.leetcode.daily import question_embed

logger = get_logger("leetcode.cog")


def build_question_embed(question: dict, is_daily: bool = False) -> discord.Embed:
    return discord.Embed.from_dict(question_embed(question, is_daily))


class LeetCodeCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db_connect):
        self.bot = bot
        self.db_connect = db_connect

    # --- DB helpers: open a session and call the service ---

    def _with_db(self, fn, *args, **kwargs):
        db = next(self.db_connect.get_db())
        try:
            return fn(db, *args, **kwargs)
        finally:
            db.close()

    def _upsert_link(self, discord_id: str, username: str):
        self._with_db(service.link, discord_id, username)

    def _get_leaderboard(self, limit: int = 10) -> list[tuple[str, str, int]]:
        return self._with_db(service.leaderboard, limit)

    def _get_server_stats(self) -> dict:
        return self._with_db(service.stats)

    def _delete_link(self, discord_id: str) -> bool:
        return self._with_db(service.unlink, discord_id)

    # --- Slash commands ---

    @discord.slash_command(name="daily", description="Get today's LeetCode daily challenge")
    async def daily(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        try:
            question = await fetch_daily_question()
            embed = build_question_embed(question, is_daily=True)
            await ctx.followup.send(embed=embed)
        except Exception:
            logger.error("Failed to fetch daily question", exc_info=True)
            await ctx.followup.send("❌ Failed to fetch the daily challenge. Try again later.")

    @discord.slash_command(name="random", description="Get a random LeetCode problem")
    async def random(
        self,
        ctx: discord.ApplicationContext,
        difficulty: Annotated[
            str | None,
            discord.Option(
                str,
                description="Filter by difficulty",
                choices=["Easy", "Medium", "Hard"],
                required=False,
                default=None,
            ),
        ] = None,
    ):
        await ctx.defer()
        try:
            question = await fetch_random_question(difficulty)
            embed = build_question_embed(question, is_daily=False)
            await ctx.followup.send(embed=embed)
        except Exception:
            logger.error("Failed to fetch random question", exc_info=True)
            await ctx.followup.send("❌ Failed to fetch a random problem. Try again later.")

    @discord.slash_command(name="link", description="Link your LeetCode handle for auto-verification")
    async def link(
        self,
        ctx: discord.ApplicationContext,
        username: Annotated[str, discord.Option(str, description="Your LeetCode username")],
    ):
        await ctx.defer(ephemeral=True)
        username = username.strip()
        if not username:
            await ctx.followup.send("❌ Username cannot be empty.", ephemeral=True)
            return

        # An unknown username makes the submissions fetch raise RuntimeError
        try:
            await fetch_recent_ac_submissions(username, limit=1)
        except RuntimeError as exc:
            msg = str(exc)
            if "not found" in msg.lower():
                await ctx.followup.send(f"❌ LeetCode username `{username}` not found.", ephemeral=True)
            else:
                logger.error(f"Failed to validate LeetCode handle '{username}'", exc_info=True)
                await ctx.followup.send(
                    f"❌ Couldn't reach LeetCode to verify `{username}`. Try again later.",
                    ephemeral=True,
                )
            return

        discord_id = str(ctx.author.id)
        self._upsert_link(discord_id, username)

        await ctx.followup.send(f"✅ Linked your Discord account to **{username}**.", ephemeral=True)

    @discord.slash_command(name="unlink", description="Remove your LeetCode handle link")
    async def unlink(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        discord_id = str(ctx.author.id)
        deleted = self._delete_link(discord_id)
        if deleted:
            await ctx.followup.send("✅ Your LeetCode link has been removed.", ephemeral=True)
        else:
            await ctx.followup.send("ℹ️ You don't have a linked LeetCode account.", ephemeral=True)

    @discord.slash_command(name="leaderboard", description="Top LeetCode daily solvers in this server")
    async def leaderboard(
        self,
        ctx: discord.ApplicationContext,
        limit: Annotated[
            int, discord.Option(int, description="How many entries to show (1-25)", required=False, default=10)
        ] = 10,
    ):
        await ctx.defer()
        limit = max(1, min(int(limit), 25))
        rows = self._get_leaderboard(limit=limit)

        embed = discord.Embed(
            title="🏆 LeetCode Daily Leaderboard",
            color=0x5865F2,
        )

        if not rows:
            embed.description = "No daily challenges solved yet. Be the first!"
            await ctx.followup.send(embed=embed)
            return

        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        lines = []
        for i, (discord_id, username, count) in enumerate(rows):
            prefix = medals.get(i, f"`#{i + 1}`")
            display = self._resolve_display_name(ctx.guild, discord_id, username)
            lines.append(f"{prefix} **{display}** (`{username}`) — {count} solved")
        embed.description = "\n".join(lines)
        await ctx.followup.send(embed=embed)

    def _resolve_display_name(self, guild: discord.Guild | None, discord_id: str, fallback: str) -> str:
        if guild is None:
            return fallback
        try:
            member = guild.get_member(int(discord_id))
        except (TypeError, ValueError):
            return fallback
        if member is None:
            return fallback
        return member.display_name

    @discord.slash_command(name="stats", description="Server-wide LeetCode stats")
    async def stats(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        s = self._get_server_stats()

        embed = discord.Embed(title="📊 LeetCode Server Stats", color=0x00B8A3)
        embed.add_field(name="Linked users", value=str(s["total_linked"]), inline=True)
        embed.add_field(name="Active solvers", value=str(s["distinct_solvers"]), inline=True)
        embed.add_field(name="Problems solved", value=str(s["total_solves"]), inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ctx.followup.send(embed=embed)
