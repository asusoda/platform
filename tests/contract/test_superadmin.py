"""Superadmin: adding an org for a Discord server."""

from modules.superadmin.service import prefix_for

from .test_access import SUPERADMIN_ID, headers_for


class Guilds:
    def __init__(self, ready=True, guild=None):
        self.ready, self.guild = ready, guild

    def is_ready(self):
        return self.ready

    def get_guild(self, guild_id):
        return self.guild


def test_prefix_follows_the_prefix_rules():
    assert prefix_for("Robotics Club @ ASU!", 1) == "robotics_club_asu"
    assert prefix_for("A" * 40, 1) == "a" * 20
    assert prefix_for("$$", 123456789) == "org_456789"


def test_add_org_errors(client, monkeypatch, app):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    headers = headers_for(SUPERADMIN_ID)

    monkeypatch.setattr(app, "discord_directory", Guilds(ready=False))
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 503

    monkeypatch.setattr(app, "discord_directory", Guilds())
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 404

    taken = {"id": "77", "name": "AIS", "icon_url": None}
    monkeypatch.setattr(app, "discord_directory", Guilds(guild=taken))
    assert client.post("/api/superadmin/add_org/77", headers=headers).status_code == 409
