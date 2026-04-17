import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord.ext import commands, tasks

from modules.bot.discord_modules.utils.leetcode import fetch_daily_question, fetch_random_question
from modules.utils.logging_config import get_logger

logger = get_logger("bot.leetcodecog")

DIFFICULTY_COLORS = {
    "Easy": 0x00B8A3,
    "Medium": 0xFFC01E,
    "Hard": 0xFF375F,
}


def build_question_embed(question: dict, is_daily: bool = False) -> discord.Embed:
    url = f"https://leetcode.com/problems/{question['titleSlug']}/"
    tags = " ".join(f"`{t['name']}`" for t in question.get("topicTags", [])) or "None"
    color = DIFFICULTY_COLORS.get(question.get("difficulty", ""), 0x5865F2)
    title_prefix = "Daily Challenge" if is_daily else "Random Problem"

    embed = discord.Embed(
        title=f"{'📅' if is_daily else '🎲'} {title_prefix} — {question['title']}",
        url=url,
        color=color,
    )
    embed.add_field(name="Difficulty", value=question.get("difficulty", "Unknown"), inline=True)
    embed.add_field(name="Acceptance", value=f"{question.get('acRate', 0):.1f}%", inline=True)
    embed.add_field(name="ID", value=f"#{question.get('frontendQuestionId', '?')}", inline=True)
    embed.add_field(name="Topics", value=tags, inline=False)
    embed.set_footer(text="Good luck! React with ✅ when you solve it.")
    embed.timestamp = discord.utils.utcnow()

    if question.get("paidOnly"):
        embed.description = "⚠️ This is a **premium** problem (LeetCode Plus required)."

    return embed


class LeetCodeCog(commands.Cog):
    def __init__(
        self, bot: commands.Bot, channel_id: int | None, role_ping: int | None, daily_time: str, timezone: str
    ):
        self.bot = bot
        self.channel_id = channel_id
        self.role_ping = role_ping
        self.daily_time = daily_time
        self.timezone = timezone
        self._daily_task_started = False
        logger.info(f"LeetCodeCog initialized (channel={channel_id}, time={daily_time}, tz={timezone})")

    def cog_unload(self):
        self.post_daily.cancel()

    async def _start_daily_task(self):
        if self._daily_task_started or not self.channel_id:
            return

        try:
            tz = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            logger.warning(f"Unknown timezone '{self.timezone}', falling back to UTC")
            tz = ZoneInfo("UTC")

        try:
            hour, minute = (int(x) for x in self.daily_time.split(":")[:2])
        except (ValueError, AttributeError):
            logger.warning(f"Invalid LEETCODE_DAILY_TIME '{self.daily_time}', defaulting to 09:00")
            hour, minute = 9, 0

        try:
            post_time = datetime.time(hour=hour, minute=minute, tzinfo=tz)
        except ValueError:
            logger.warning(f"Invalid LEETCODE_DAILY_TIME '{self.daily_time}', defaulting to 09:00")
            post_time = datetime.time(hour=9, minute=0, tzinfo=tz)
        self.post_daily.change_interval(time=post_time)
        self.post_daily.start()
        self._daily_task_started = True
        logger.info(f"Daily LeetCode task scheduled at {post_time}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self._start_daily_task()

    @tasks.loop(hours=24)
    async def post_daily(self):
        if not self.channel_id:
            return

        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.channel_id)
            except Exception:
                logger.error(f"LeetCode channel {self.channel_id} not found")
                return

        if not callable(getattr(channel, "send", None)):
            logger.error(f"LeetCode channel {self.channel_id} is not a text-capable channel")
            return

        try:
            question = await fetch_daily_question()
            embed = build_question_embed(question, is_daily=True)
            content = f"<@&{self.role_ping}>" if self.role_ping else None
            msg = await channel.send(content=content, embed=embed)
            await msg.add_reaction("✅")
            logger.info(f"Posted daily LeetCode: {question['title']}")
        except Exception:
            logger.error("Failed to post daily LeetCode question", exc_info=True)

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
