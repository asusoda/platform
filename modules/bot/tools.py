"""Discord tools: read the org's Discord server with the bot token, as an officer would browse it.

Every call checks that the channel belongs to the org's server. The bot reads only what its own Discord
permissions let it see. Nothing here writes to Discord.
"""

from datetime import UTC, datetime, timedelta

from core.integrations.discord import DiscordDirectory, DiscordUnavailable
from core.tools import ToolError, tool
from modules.auth import scopes
from modules.users import service as users

scopes.declare("discord:read", "Read the org's Discord server: channels, messages, pins and members")

SCOPE = "discord:read"
# Discord's epoch for message ids (snowflakes), in milliseconds
DISCORD_EPOCH_MS = 1_420_070_400_000
VIEW_CHANNEL = 1 << 10
MAX_MESSAGES = 500
MAX_SCANNED = 2000
MAX_CONTENT = 2000
KINDS = {0: "text", 2: "voice", 4: "category", 5: "announcement", 10: "thread", 11: "thread", 12: "thread", 13: "stage"}
KINDS |= {15: "forum", 16: "media"}

ID = {"type": "string", "pattern": "^[0-9]{5,25}$"}
DAYS = {"type": "integer", "minimum": 1, "maximum": 90, "description": "Only messages from the last days days"}


def _directory() -> DiscordDirectory:
    return users.bot_directory()


def _guild(org) -> str:
    if not org.guild_id:
        raise ToolError("This org has no Discord server", 400)
    return str(org.guild_id)


def _run(func):
    try:
        return func()
    except DiscordUnavailable as e:
        raise ToolError(f"Discord: {e}", 502) from e


def _snowflake(when: datetime) -> str:
    return str((int(when.timestamp() * 1000) - DISCORD_EPOCH_MS) << 22)


def _private(channel: dict, guild_id: str) -> bool:
    """Whether @everyone cannot view the channel: an officer or staff channel."""
    for overwrite in channel.get("permission_overwrites") or []:
        if str(overwrite.get("id")) == guild_id and int(overwrite.get("deny", 0)) & VIEW_CHANNEL:
            return True
    return False


def _channel_row(channel: dict, guild_id: str) -> dict:
    return {
        "id": str(channel["id"]),
        "name": channel.get("name"),
        "kind": KINDS.get(int(channel.get("type", 0)), "other"),
        "parent_id": str(channel["parent_id"]) if channel.get("parent_id") else None,
        "topic": channel.get("topic"),
        "private": _private(channel, guild_id),
    }


def _own_channel(directory: DiscordDirectory, guild_id: str, channel_id: str) -> dict:
    """The channel when it is in the org's server. Same answer for missing and another server's."""
    channel = directory.get_channel(channel_id)
    if not channel or str(channel.get("guild_id")) != guild_id:
        raise ToolError(f"No channel {channel_id} in this org's Discord server", 404)
    return channel


def _message_row(message: dict, guild_id: str) -> dict:
    author = message.get("author") or {}
    return {
        "id": str(message["id"]),
        "channel_id": str(message["channel_id"]),
        "author": author.get("global_name") or author.get("username"),
        "author_id": str(author.get("id", "")),
        "bot": bool(author.get("bot")),
        "at": message.get("timestamp"),
        "content": (message.get("content") or "")[:MAX_CONTENT],
        "attachments": [a.get("filename") for a in message.get("attachments") or []],
        "embeds": [e.get("title") for e in message.get("embeds") or [] if e.get("title")],
        "reply_to": str((message.get("message_reference") or {}).get("message_id") or "") or None,
        "url": f"https://discord.com/channels/{guild_id}/{message['channel_id']}/{message['id']}",
    }


def _history(directory, channel_id: str, limit: int, before: str | None, since: str | None) -> list[dict]:
    """Up to limit messages, newest first, older than before and newer than since."""
    found: list[dict] = []
    while len(found) < limit:
        page = directory.messages(channel_id, limit=min(100, limit - len(found)), before=before)
        if not page:
            break
        page = sorted(page, key=lambda m: int(m["id"]), reverse=True)
        fresh = [m for m in page if since is None or int(m["id"]) > int(since)]
        found += fresh
        if len(fresh) < len(page) or len(page) < 100:
            break
        before = str(page[-1]["id"])
    return found[:limit]


@tool(
    "discord.server",
    description="The org's Discord server: name, roles, and how many channels of each kind it has.",
    scope=SCOPE,
)
def discord_server(db, org, caller):
    directory = _directory()
    guild_id = _guild(org)

    def read():
        guild = directory.get_guild(guild_id) or {}
        channels = directory.get_channels(guild_id)
        counts: dict[str, int] = {}
        for channel in channels:
            kind = KINDS.get(int(channel.get("type", 0)), "other")
            counts[kind] = counts.get(kind, 0) + 1
        roles = [{"id": r["id"], "name": r["name"]} for r in directory.get_guild_roles(guild_id)]
        return {"id": guild_id, "name": guild.get("name"), "channels": counts, "roles": roles}

    return _run(read)


@tool(
    "discord.channels",
    description=(
        "The channels of the org's Discord server by category, with id, kind, topic and private (hidden from "
        "@everyone), and the active threads. Use the id with discord.messages."
    ),
    scope=SCOPE,
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 100}},
        "additionalProperties": False,
    },
)
def discord_channels(db, org, caller, query: str | None = None):
    directory = _directory()
    guild_id = _guild(org)

    def read():
        rows = [_channel_row(c, guild_id) for c in directory.get_channels(guild_id)]
        threads = [_channel_row(t, guild_id) for t in directory.active_threads(guild_id)]
        names = {c["id"]: c["name"] for c in rows if c["kind"] == "category"}
        channels = [c for c in rows if c["kind"] != "category"]
        if query:
            text = query.lower().lstrip("#")
            channels = [c for c in channels if text in (c["name"] or "").lower()]
            threads = [t for t in threads if text in (t["name"] or "").lower()]
        for row in channels + threads:
            row["category"] = names.get(row["parent_id"] or "")
        channels.sort(key=lambda c: (c["category"] or "", c["name"] or ""))
        return {"channels": channels, "threads": threads}

    return _run(read)


@tool(
    "discord.messages",
    description=(
        "Messages of one channel or thread of the org's server, newest first: author, time, text, attachments "
        "and a link. days keeps the last days only; before is a message id to page back from."
    ),
    scope=SCOPE,
    input_schema={
        "type": "object",
        "properties": {
            "channel_id": ID,
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_MESSAGES},
            "days": DAYS,
            "before": ID,
        },
        "required": ["channel_id"],
        "additionalProperties": False,
    },
)
def discord_messages(db, org, caller, channel_id: str, limit: int = 50, days: int | None = None, before=None):
    directory = _directory()
    guild_id = _guild(org)

    def read():
        channel = _own_channel(directory, guild_id, channel_id)
        since = _snowflake(datetime.now(UTC) - timedelta(days=days)) if days else None
        found = _history(directory, channel_id, limit, before, since)
        rows = [_message_row(m, guild_id) for m in found]
        return {
            "channel": {"id": channel_id, "name": channel.get("name")},
            "messages": rows,
            "next_before": rows[-1]["id"] if len(rows) == limit else None,
        }

    return _run(read)


@tool(
    "discord.search",
    description=(
        "Find messages in the org's server whose text has every word of query. Reads the recent history of the "
        "channels you name, or of every text channel the bot sees, up to 2000 messages. days narrows it."
    ),
    scope=SCOPE,
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "channel_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 20},
            "author_id": ID,
            "days": DAYS,
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def discord_search(db, org, caller, query: str, channel_ids=None, author_id=None, days: int = 30, limit: int = 25):
    directory = _directory()
    guild_id = _guild(org)
    words = [w for w in query.lower().split() if w]

    def read():
        if channel_ids:
            targets = [str(_own_channel(directory, guild_id, c)["id"]) for c in channel_ids]
        else:
            readable = [c for c in directory.get_channels(guild_id) if int(c.get("type", 0)) in (0, 5)]
            targets = [str(c["id"]) for c in readable]
        since = _snowflake(datetime.now(UTC) - timedelta(days=days))
        per_channel = max(100, MAX_SCANNED // max(1, len(targets)))
        found, scanned, skipped = [], 0, []
        for target in targets:
            if scanned >= MAX_SCANNED:
                skipped.append(target)
                continue
            try:
                history = _history(directory, target, min(per_channel, MAX_SCANNED - scanned), None, since)
            except DiscordUnavailable:
                # A channel the bot cannot read
                skipped.append(target)
                continue
            scanned += len(history)
            for message in history:
                text = (message.get("content") or "").lower()
                if all(w in text for w in words) and (
                    author_id is None or str((message.get("author") or {}).get("id")) == author_id
                ):
                    found.append(_message_row(message, guild_id))
        found.sort(key=lambda m: int(m["id"]), reverse=True)
        return {"matches": found[:limit], "scanned": scanned, "channels": len(targets), "skipped": skipped}

    return _run(read)


@tool(
    "discord.pins",
    description="The pinned messages of one channel of the org's server.",
    scope=SCOPE,
    input_schema={
        "type": "object",
        "properties": {"channel_id": ID},
        "required": ["channel_id"],
        "additionalProperties": False,
    },
)
def discord_pins(db, org, caller, channel_id: str):
    directory = _directory()
    guild_id = _guild(org)

    def read():
        _own_channel(directory, guild_id, channel_id)
        return {"pins": [_message_row(m, guild_id) for m in directory.pins(channel_id)]}

    return _run(read)


@tool(
    "discord.members",
    description=(
        "Members of the org's server whose username or nickname starts with query, with their role ids. "
        "Needs the Server Members intent."
    ),
    scope=SCOPE,
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 100},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def discord_members(db, org, caller, query: str, limit: int = 20):
    directory = _directory()
    guild_id = _guild(org)
    return _run(lambda: {"members": directory.search_members(guild_id, query, limit)})
