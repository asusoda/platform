"""Type stubs for shared module."""
from typing import Any
from flask import Flask
from modules.bot.discord_modules.bot import BotFork
from modules.calendar.service import MultiOrgCalendarService
from modules.utils.TokenManager import TokenManager
from modules.utils.db import DBConnect
from modules.utils.config import Config
from modules.utils.logging_config import logger as logger
import asyncio

# Extended Flask app with custom attributes
class ExtendedFlask(Flask):
    auth_bot: BotFork | None
    multi_org_calendar_service: MultiOrgCalendarService

app: ExtendedFlask
config: Config
db_connect: DBConnect
tokenManger: TokenManager

def create_auth_bot(loop: asyncio.AbstractEventLoop) -> BotFork: ...
