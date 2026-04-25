import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord.ext import commands, tasks
from sqlalchemy import func as sa_func

from modules.bot.discord_modules.utils.leetcode import (
    fetch_daily_question,
    fetch_random_question,
    fetch_recent_ac_submissions,
)
from modules.bot.models import LeetCodeLink, LeetCodeSolve
from modules.utils.logging_config import get_logger

logger = get_logger("bot.leetcodecog")

DIFFICULTY_COLORS = {
    "Easy": 0x00B8A3,
    "Medium": 0xFFC01E,
    "Hard": 0xFF375F,
}

VERIFY_INTERVAL_MINUTES = 10


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
    embed.set_footer(text="Good luck! Link your account with /link to get auto-verified.")
    embed.timestamp = discord.utils.utcnow()

    if question.get("paidOnly"):
        embed.description = "⚠️ This is a **premium** problem (LeetCode Plus required)."

    return embed


class LeetCodeCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        db_connect,
        channel_id: int | None,
        role_ping: int | None,
        daily_time: str,
        timezone: str,
    ):
        self.bot = bot
        self.db_connect = db_connect
        self.channel_id = channel_id
        self.role_ping = role_ping
        self.daily_time = daily_time
        self.timezone = timezone
        self._tz = self._resolve_timezone(timezone)
        self._daily_task_started = False

        # Today's daily challenge state (reset on each daily post)
        self._today_slug: str | None = None
        self._today_date: datetime.date | None = None
        self._daily_message: discord.Message | None = None
        self._verified_today: set[str] = set()
        self._pending_today: set[str] = set()

        logger.info(f"LeetCodeCog initialized (channel={channel_id}, time={daily_time}, tz={timezone})")

    def _resolve_timezone(self, tz_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logger.warning(f"Unknown timezone '{tz_name}', falling back to UTC")
            return ZoneInfo("UTC")

    def cog_unload(self):
        self.post_daily.cancel()
        self.verify_loop.cancel()

    async def _start_daily_task(self):
        if self._daily_task_started or not self.channel_id:
            return

        try:
            hour, minute = (int(x) for x in self.daily_time.split(":")[:2])
        except (ValueError, AttributeError):
            logger.warning(f"Invalid LEETCODE_DAILY_TIME '{self.daily_time}', defaulting to 09:00")
            hour, minute = 9, 0

        try:
            post_time = datetime.time(hour=hour, minute=minute, tzinfo=self._tz)
        except ValueError:
            logger.warning(f"Invalid LEETCODE_DAILY_TIME '{self.daily_time}', defaulting to 09:00")
            post_time = datetime.time(hour=9, minute=0, tzinfo=self._tz)

        self.post_daily.change_interval(time=post_time)
        self.post_daily.start()
        self._daily_task_started = True
        logger.info(f"Daily LeetCode task scheduled at {post_time}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self._start_daily_task()

    # --- Daily post + verification orchestration ---

    @tasks.loop(hours=24)
    async def post_daily(self):
        if not self.channel_id:
            return

        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.channel_id)
            except Exception:
                logger.error(f"LeetCode channel {self.channel_id} not found", exc_info=True)
                return

        if not callable(getattr(channel, "send", None)):
            logger.error(f"LeetCode channel {self.channel_id} does not support sending messages")
            return

        try:
            question = await fetch_daily_question()
            embed = build_question_embed(question, is_daily=True)
            content = f"<@&{self.role_ping}>" if self.role_ping else None
            msg = await channel.send(content=content, embed=embed)
            await msg.add_reaction("✅")
            logger.info(f"Posted daily LeetCode: {question['title']}")

            # Reset state and prime verification poller for this new day
            self._today_slug = question["titleSlug"]
            self._today_date = datetime.datetime.now(self._tz).date()
            self._daily_message = msg
            self._verified_today = set()
            self._pending_today = set(self._get_all_linked_discord_ids())

            if self._pending_today:
                if self.verify_loop.is_running():
                    self.verify_loop.restart()
                else:
                    self.verify_loop.start()
                logger.info(
                    f"Verification poller started for {len(self._pending_today)} linked users (slug={self._today_slug})"
                )
            else:
                logger.info("No linked users; skipping verification poller")
        except Exception:
            logger.error("Failed to post daily LeetCode question", exc_info=True)

    @tasks.loop(minutes=VERIFY_INTERVAL_MINUTES)
    async def verify_loop(self):
        if not self._today_slug or not self._today_date:
            self.verify_loop.stop()
            return

        # Stop if the configured-tz date has rolled past today
        if datetime.datetime.now(self._tz).date() != self._today_date:
            logger.info("Day rolled over; stopping verification poller")
            self.verify_loop.stop()
            return

        if not self._pending_today:
            logger.info("All linked users verified for today; stopping verification poller")
            self.verify_loop.stop()
            return

        # Snapshot to avoid mutation during iteration
        pending_snapshot = list(self._pending_today)
        links = self._get_links(pending_snapshot)

        for discord_id, username in links.items():
            try:
                if await self._user_solved_today(username):
                    self._pending_today.discard(discord_id)
                    self._verified_today.add(discord_id)
                    self._record_solve(discord_id, self._today_slug, self._today_date)
                    await self._announce_verified(discord_id, username)
            except Exception:
                logger.error(f"Verification check failed for {username}", exc_info=True)

    async def _user_solved_today(self, username: str) -> bool:
        submissions = await fetch_recent_ac_submissions(username, limit=20)
        for sub in submissions:
            if sub.get("titleSlug") != self._today_slug:
                continue
            ts_raw = sub.get("timestamp")
            if ts_raw is None:
                continue
            try:
                ts = int(ts_raw)
            except (TypeError, ValueError):
                continue
            sub_date = datetime.datetime.fromtimestamp(ts, tz=self._tz).date()
            if sub_date == self._today_date:
                return True
        return False

    async def _announce_verified(self, discord_id: str, username: str):
        if not self._daily_message:
            return
        try:
            await self._daily_message.reply(
                f"✅ <@{discord_id}> solved today's challenge as **{username}**!",
                mention_author=False,
            )
            logger.info(f"Verified {discord_id} ({username}) for slug {self._today_slug}")
        except Exception:
            logger.error(f"Failed to announce verification for {discord_id}", exc_info=True)

    # --- DB helpers ---

    def _get_all_linked_discord_ids(self) -> list[str]:
        db = next(self.db_connect.get_db())
        try:
            return [row.discord_id for row in db.query(LeetCodeLink).all()]
        finally:
            db.close()

    def _get_links(self, discord_ids: list[str]) -> dict[str, str]:
        if not discord_ids:
            return {}
        db = next(self.db_connect.get_db())
        try:
            rows = db.query(LeetCodeLink).filter(LeetCodeLink.discord_id.in_(discord_ids)).all()
            return {row.discord_id: row.leetcode_username for row in rows}
        finally:
            db.close()

    def _upsert_link(self, discord_id: str, username: str):
        db = next(self.db_connect.get_db())
        try:
            existing = db.query(LeetCodeLink).filter_by(discord_id=discord_id).first()
            if existing:
                existing.leetcode_username = username
            else:
                db.add(LeetCodeLink(discord_id=discord_id, leetcode_username=username))
            db.commit()
        finally:
            db.close()

    def _record_solve(self, discord_id: str, title_slug: str, solved_date: datetime.date):
        db = next(self.db_connect.get_db())
        try:
            existing = db.query(LeetCodeSolve).filter_by(discord_id=discord_id, solved_date=solved_date).first()
            if existing:
                return
            db.add(LeetCodeSolve(discord_id=discord_id, title_slug=title_slug, solved_date=solved_date))
            db.commit()
        except Exception:
            logger.error(f"Failed to record solve for {discord_id}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _get_leaderboard(self, limit: int = 10) -> list[tuple[str, str, int]]:
        """Returns [(discord_id, leetcode_username, solve_count), ...] sorted desc."""
        db = next(self.db_connect.get_db())
        try:
            rows = (
                db.query(
                    LeetCodeSolve.discord_id,
                    LeetCodeLink.leetcode_username,
                    sa_func.count(LeetCodeSolve.id).label("solve_count"),
                )
                .outerjoin(LeetCodeLink, LeetCodeLink.discord_id == LeetCodeSolve.discord_id)
                .group_by(LeetCodeSolve.discord_id, LeetCodeLink.leetcode_username)
                .order_by(sa_func.count(LeetCodeSolve.id).desc())
                .limit(limit)
                .all()
            )
            return [(r[0], r[1] or "(unlinked)", r[2]) for r in rows]
        finally:
            db.close()

    def _get_server_stats(self) -> dict:
        db = next(self.db_connect.get_db())
        try:
            total_linked = db.query(LeetCodeLink).count()
            total_solves = db.query(LeetCodeSolve).count()
            distinct_solvers = db.query(sa_func.count(sa_func.distinct(LeetCodeSolve.discord_id))).scalar() or 0
            return {
                "total_linked": total_linked,
                "total_solves": total_solves,
                "distinct_solvers": distinct_solvers,
            }
        finally:
            db.close()

    def _delete_link(self, discord_id: str) -> bool:
        db = next(self.db_connect.get_db())
        try:
            existing = db.query(LeetCodeLink).filter_by(discord_id=discord_id).first()
            if not existing:
                return False
            db.delete(existing)
            db.commit()
            return True
        finally:
            db.close()

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

        # Validate by fetching recent AC submissions — raises RuntimeError for invalid usernames
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

        # If a daily challenge is in progress, opt this user into the current poll
        if self._today_slug and self._today_date == datetime.datetime.now(self._tz).date():
            if discord_id not in self._verified_today:
                self._pending_today.add(discord_id)
                if not self.verify_loop.is_running():
                    self.verify_loop.start()

        await ctx.followup.send(f"✅ Linked your Discord account to **{username}**.", ephemeral=True)

    @discord.slash_command(name="unlink", description="Remove your LeetCode handle link")
    async def unlink(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        discord_id = str(ctx.author.id)
        deleted = self._delete_link(discord_id)
        self._pending_today.discard(discord_id)
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
