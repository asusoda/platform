from __future__ import annotations

import os
from typing import TYPE_CHECKING

from flask import Flask
from flask_cors import CORS

if TYPE_CHECKING:
    from modules.bot.discord_modules.bot import BotFork
    from modules.calendar.service import MultiOrgCalendarService


class ExtendedFlask(Flask):
    auth_bot: BotFork | None
    multi_org_calendar_service: MultiOrgCalendarService


app = ExtendedFlask(
    "SoDA internal API",
    static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web", "build")),
    template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web", "build")),
)
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://thesoda.io",
                "https://admin.thesoda.io",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Organization-ID", "X-Organization-Prefix"],
            "supports_credentials": True,
        }
    },
)
