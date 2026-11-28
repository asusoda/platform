"""Jeopardy in Discord: one game for each org, kept in active_game across a restart, and games stored per org.

SoDA is guild 1001 and AI Society guild 1002 (see conftest).
"""

import asyncio
import copy
import itertools
import logging
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from tests.contract.conftest import OFFICER_DISCORD_ID

AIS_OFFICER_ID = "900000000000000003"
SUPERADMIN_ID = "900000000000000009"
OFFICER_GUILDS = {OFFICER_DISCORD_ID: [1001], AIS_OFFICER_ID: [1002]}

GAME: dict[str, Any] = {
    "game": {
        "name": "Trivia Night",
        "description": "Questions",
        "players": 4,
        "categories": ["Code"],
        "per_category": 1,
        "teams": ["Red", "Blue"],
        "uuid": "game-1",
    },
    "questions": {"Code": [{"question": "2+2?", "answer": "4", "value": 100, "uuid": "q-1"}]},
}

ids = itertools.count(5000)


def _game(name: str) -> dict:
    game = copy.deepcopy(GAME)
    game["game"]["name"] = name
    return game


class FakeRole:
    def __init__(self, guild, name):
        self.id, self.name, self.guild = next(ids), name, guild

    async def delete(self):
        self.guild.roles.pop(self.id, None)


class FakeMessage:
    def __init__(self, kwargs):
        self.id = next(ids)
        self.sent = kwargs
        self.views: list = []

    async def add_reaction(self, emoji):
        return None

    async def edit(self, **kwargs):
        if "view" in kwargs:
            self.views.append(kwargs["view"])


class FakeChannel:
    def __init__(self, guild, name):
        self.id, self.name, self.guild = next(ids), name, guild
        self.messages: dict[int, FakeMessage] = {}

    async def edit(self, **kwargs):
        return None

    async def send(self, **kwargs):
        message = FakeMessage(kwargs)
        self.messages[message.id] = message
        return message

    async def fetch_message(self, message_id):
        if message_id not in self.messages:
            raise discord.NotFound(cast(Any, SimpleNamespace(status=404, reason="Not Found")), "Unknown Message")
        return self.messages[message_id]

    async def delete(self):
        self.guild.channels.pop(self.id, None)


class FakeGuild:
    def __init__(self, guild_id, name="Guild"):
        self.id, self.name = guild_id, name
        self.default_role = FakeRole(self, "@everyone")
        self.channels: dict[int, FakeChannel] = {}
        self.roles: dict[int, FakeRole] = {}
        self.members: dict[int, Any] = {}

    def _channel(self, name):
        channel = FakeChannel(self, name)
        self.channels[channel.id] = channel
        return channel

    @property
    def created(self) -> list[str]:
        return [c.name for c in self.channels.values()] + [r.name for r in self.roles.values()]

    async def create_category(self, name):
        return self._channel(name)

    async def create_stage_channel(self, name, **kwargs):
        return self._channel(name)

    async def create_voice_channel(self, name, **kwargs):
        return self._channel(name)

    async def create_text_channel(self, name, **kwargs):
        return self._channel(name)

    async def create_role(self, name):
        role = FakeRole(self, name)
        self.roles[role.id] = role
        return role

    def get_channel(self, channel_id):
        return self.channels.get(channel_id)

    def get_role(self, role_id):
        return self.roles.get(role_id)

    def get_member(self, member_id):
        return self.members.get(member_id)


class FakeBot:
    def __init__(self, *guilds):
        self.guilds = list(guilds)
        self.executed: list[tuple] = []

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)

    def execute(self, *args, **kwargs):
        self.executed.append(args)


def _player(guild: FakeGuild, n: int):
    member = SimpleNamespace(id=n, display_name=f"p{n}", roles=[])
    guild.members[n] = member
    return cast(discord.Member, member)


def _org_id(prefix: str) -> int:
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return db.query(Organization).filter_by(prefix=prefix).one().id
    finally:
        db.close()


def _rows():
    from core.db import db_connect
    from modules.bot.submodules.games import service

    db = db_connect.SessionLocal()
    try:
        return {row.organization_id: row for row in service.states(db)}
    finally:
        db.close()


def _headers(discord_id):
    from modules.auth.tokens import token_manager

    return {"Authorization": f"Bearer {token_manager.generate_token(username='u', discord_id=discord_id)}"}


class ScopedDirectory:
    """Each user is an officer only in the guilds in OFFICER_GUILDS."""

    def is_ready(self):
        return True

    def officer_guilds(self, user_id, org_roles):
        return OFFICER_GUILDS.get(str(user_id), [])


@pytest.fixture(autouse=True)
def clean_games(app, monkeypatch):
    """Officers by OFFICER_GUILDS, SUPERADMIN_ID as the superadmin, and no stored or active game after the test."""
    from core.config import config
    from core.db import db_connect
    from modules.auth import access
    from modules.bot.submodules.games.models import ActiveGame, JeopardyGame

    access.clear_cache()
    monkeypatch.setattr(app, "discord_directory", ScopedDirectory())
    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    yield
    access.clear_cache()
    db = db_connect.SessionLocal()
    db.query(ActiveGame).delete()
    db.query(JeopardyGame).delete()
    db.commit()
    db.close()


def test_announcement_location_names_the_org_or_the_server(app):
    from modules.bot.submodules.games.session import server_name

    assert server_name(cast(discord.Guild, SimpleNamespace(id=1002, name="Guild Name"))) == "AI Society"
    assert server_name(cast(discord.Guild, SimpleNamespace(id=9999, name="Guild Name"))) == "Guild Name"


def test_balance_teams_puts_each_player_in_one_team():
    from modules.bot.submodules.games.jeopardy.game import JeopardyGame
    from modules.bot.submodules.games.session import GameSession

    guild = FakeGuild(1001)
    session = GameSession(org_id=1, guild=cast(discord.Guild, guild), game=JeopardyGame(GAME))
    for n in range(5):
        session.game.add_member(_player(guild, n))
    session.balance_teams()
    placed = [member.id for team in session.game.teams for member in team.members]
    assert sorted(placed) == [0, 1, 2, 3, 4]
    assert sorted(len(team.members) for team in session.game.teams) == [2, 3]


def _set_up(cog, prefix: str, guild: FakeGuild, game: dict):
    cog.set_game(_org_id(prefix), cast(discord.Guild, guild), game, "Friday", "6 PM")
    assert asyncio.run(cog.setup_game(guild.id))
    return cog.session(guild.id)


def test_two_orgs_run_games_at_once_and_a_restart_keeps_both(app, caplog):
    from modules.bot.submodules.games.cog import GameCog

    soda, ais = FakeGuild(1001), FakeGuild(1002)
    bot = FakeBot(soda, ais)
    cog = GameCog(cast(Any, bot))
    first = _set_up(cog, "soda", soda, _game("SoDA Night"))
    second = _set_up(cog, "ais", ais, _game("AIS Night"))
    assert first is not second and cog.is_setup(1001) and cog.is_setup(1002)
    for n in range(3):
        cog.add_member(1001, _player(soda, n))
    cog.add_member(1002, _player(ais, 7))
    assert asyncio.run(first.start())
    uuid = first.game.questions["Code"][0].id
    assert asyncio.run(first.show_question(uuid))
    assert asyncio.run(first.award_points("Red", 300))
    assert not second.game.is_started and "scoreboard" in soda.created and "scoreboard" not in ais.created

    rows = _rows()
    assert {rows[_org_id("soda")].name, rows[_org_id("ais")].name} == {"SoDA Night", "AIS Night"}
    assert rows[_org_id("soda")].guild_id == "1001"

    # The AI Society stage is deleted while the bot is down
    del ais.channels[second.stage.id]
    question = first.question_post[uuid]["message"]

    restarted = GameCog(cast(Any, bot))
    with caplog.at_level(logging.WARNING):
        asyncio.run(restarted.restore())
    soda_game, ais_game = restarted.session(1001), restarted.session(1002)
    assert soda_game is not None and ais_game is not None
    assert soda_game.game.is_started and soda_game.game.to_json() == first.game.to_json()
    assert sorted(p.id for p in soda_game.game.players) == [0, 1, 2]
    assert [t.score for t in soda_game.game.teams] == [300, 0]
    assert {t.role.name for t in soda_game.game.teams if t.role} == {"Red", "Blue"}
    assert soda_game.scoreboard is not None and soda_game.question_post[uuid]["message"] is question
    assert question.views, "the buzz-in view is put back on the question post"
    assert ais_game.stage is None and ais_game.announcement_channel is not None
    assert [p.id for p in ais_game.game.players] == [7]
    assert "stage=" in caplog.text
    signups = [args[2] for args in bot.executed if args[1] == "add_to_listner"]
    assert soda_game.signup in signups and ais_game.signup in signups

    assert asyncio.run(restarted.clear_game(1002))
    assert set(_rows()) == {_org_id("soda")} and ais.created == []
    assert restarted.is_setup(1001)


def _upload(client, headers, name: str, org: str | None = None):
    import io
    import json

    query = f"?org={org}" if org else ""
    data = {"file": (io.BytesIO(json.dumps(_game(name)).encode()), "game.json")}
    return client.post(f"/api/bot/uploadgame{query}", data=data, headers=headers, content_type="multipart/form-data")


def test_officer_sees_only_the_games_of_their_org(client):
    soda, ais = _headers(OFFICER_DISCORD_ID), _headers(AIS_OFFICER_ID)
    assert _upload(client, soda, "SoDA Night").status_code == 200
    assert _upload(client, ais, "AIS Night").status_code == 200

    listed = client.get("/api/bot/getavailablegames", headers=soda)
    assert listed.status_code == 200
    assert listed.get_json() == [{"name": "SoDA Night", "description": "Questions", "uuid": "game-1"}]
    assert client.get("/api/bot/getgame?name=AIS%20Night", headers=soda).status_code == 404
    assert client.get("/api/bot/getgame?name=SoDA%20Night", headers=soda).get_json()["info"]["name"] == "SoDA Night"
    assert client.get("/api/bot/getavailablegames?org=ais", headers=soda).status_code == 400
    assert _upload(client, soda, "Sneaky", org="ais").status_code == 400
    assert [g["name"] for g in client.get("/api/bot/getavailablegames", headers=ais).get_json()] == ["AIS Night"]


def test_superadmin_must_name_the_org(client):
    admin = _headers(SUPERADMIN_ID)
    assert _upload(client, _headers(AIS_OFFICER_ID), "AIS Night").status_code == 200

    refused = client.get("/api/bot/getavailablegames", headers=admin)
    assert refused.status_code == 400 and "org" in refused.get_json()["error"]
    assert _upload(client, admin, "Nowhere").status_code == 400
    assert client.get("/api/bot/getavailablegames?org=soda", headers=admin).get_json() == []
    assert [g["name"] for g in client.get("/api/bot/getavailablegames?org=ais", headers=admin).get_json()] == [
        "AIS Night"
    ]
    assert client.get("/api/bot/getavailablegames?guild_id=1002", headers=admin).status_code == 200


def test_two_officers_set_up_games_in_their_own_servers(client, monkeypatch):
    from modules.bot.submodules.games import api
    from modules.bot.submodules.games.cog import GameCog

    soda, ais = _headers(OFFICER_DISCORD_ID), _headers(AIS_OFFICER_ID)
    assert _upload(client, soda, "SoDA Night").status_code == 200
    assert _upload(client, ais, "AIS Night").status_code == 200
    soda_guild, ais_guild = FakeGuild(1001), FakeGuild(1002)
    bot = FakeBot(soda_guild, ais_guild)
    cog = GameCog(cast(Any, bot))
    monkeypatch.setattr(api, "_ready_bot", lambda: bot)
    monkeypatch.setattr(api, "_game_cog", lambda bot: cog)

    assert client.post("/api/bot/setactivegame?name=SoDA%20Night", headers=soda).status_code == 200
    assert client.post("/api/bot/setactivegame?name=SoDA%20Night", headers=ais).status_code == 404
    assert client.post("/api/bot/setactivegame?name=AIS%20Night", headers=ais).status_code == 200
    assert client.post("/api/bot/setactivegame?name=SoDA%20Night", headers=soda).status_code == 409
    assert "Jeopardy" in soda_guild.created and "Jeopardy" in ais_guild.created
    assert client.get("/api/bot/getactivegame", headers=soda).get_json()["game"]["name"] == "SoDA Night"
    assert client.get("/api/bot/getactivegamestate", headers=ais).get_json()["game"]["name"] == "AIS Night"

    cog.add_member(1001, _player(soda_guild, 1))
    assert client.post("/api/bot/startactivegame", headers=soda).status_code == 200
    soda_game, ais_game = cog.session(1001), cog.session(1002)
    assert soda_game is not None and ais_game is not None
    assert soda_game.game.is_started and not ais_game.game.is_started
    assert client.post("/api/bot/awardpoints?team=Red&points=x", headers=soda).status_code == 400

    assert client.post("/api/bot/cleanactivegame", headers=ais).status_code == 200
    assert cog.session(1002) is None and cog.session(1001) is not None
    assert client.post("/api/bot/startactivegame", headers=ais).status_code == 400
    assert set(_rows()) == {_org_id("soda")}
