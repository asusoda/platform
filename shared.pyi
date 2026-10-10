"""Type stubs for shared module."""

import asyncio

from flask import Flask
from notion_client import Client as NotionClient

from core.config import Config
from core.db import DBConnect
from core.discord_directory import DiscordDirectory
from core.logging_config import logger as logger
from core.TokenManager import TokenManager
from modules.bot.discord_modules.bot import BotFork
from modules.calendar.service import MultiOrgCalendarService

# Extended Flask app with custom attributes
class ExtendedFlask(Flask):
    auth_bot: BotFork | None
    discord_directory: DiscordDirectory
    multi_org_calendar_service: MultiOrgCalendarService

app: ExtendedFlask
config: Config
db_connect: DBConnect
tokenManager: TokenManager
notion: NotionClient

def create_auth_bot(loop: asyncio.AbstractEventLoop) -> BotFork: ...
