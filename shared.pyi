"""Type stubs for shared module."""

import asyncio

from flask import Flask
from notion_client import Client as NotionClient

from modules.bot.discord_modules.bot import BotFork
from modules.calendar.service import MultiOrgCalendarService
from modules.utils.config import Config
from modules.utils.db import DBConnect
from modules.utils.logging_config import logger as logger
from modules.utils.TokenManager import TokenManager

# Extended Flask app with custom attributes
class ExtendedFlask(Flask):
    auth_bot: BotFork | None
    multi_org_calendar_service: MultiOrgCalendarService

app: ExtendedFlask
config: Config
db_connect: DBConnect
tokenManager: TokenManager
notion: NotionClient

def create_auth_bot(loop: asyncio.AbstractEventLoop) -> BotFork: ...
