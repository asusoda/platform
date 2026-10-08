"""Org branding: a logo URL and accent color in config.branding, read and set by officers on the dashboard."""

import pytest

from tests.contract.conftest import OFFICER_DISCORD_ID
from tests.contract.test_access import AIS_OFFICER_ID, SUPERADMIN_ID, ScopedBot, headers_for


class FakeDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def make_org(config=None):
    from modules.organizations.models import Organization

    return Organization(name="Org", prefix="org", guild_id="1", config=config)


def test_unset_branding_is_none():
    from modules.organizations import service

    assert service.branding(make_org()) == {"logo_url": None, "accent_color": None}
    assert service.branding(make_org({"branding": {"logo_url": ""}})) == {"logo_url": None, "accent_color": None}


def test_set_branding_saves_and_normalizes():
    from modules.organizations import service

    org, db = make_org({"modules": {"points": False}}), FakeDB()
    saved = service.set_branding(db, org, {"logo_url": "https://cdn.example.org/logo.png", "accent_color": "#1F6FEB"})
    assert saved == {"logo_url": "https://cdn.example.org/logo.png", "accent_color": "#1f6feb"}
    assert org.config["modules"] == {"points": False}
    assert db.commits == 1

    assert service.set_branding(db, org, {"accent_color": ""}) == {
        "logo_url": "https://cdn.example.org/logo.png",
        "accent_color": None,
    }
    assert service.set_branding(db, org, {"logo_url": None})["logo_url"] is None
    assert org.config["branding"] == {}


@pytest.mark.parametrize(
    "changes",
    [
        None,
        {},
        [],
        {"theme": "dark"},
        {"accent_color": "red"},
        {"accent_color": "#fff"},
        {"accent_color": "#12345g"},
        {"accent_color": "#1234567"},
        {"accent_color": "#123456\n"},
        {"accent_color": 123456},
        {"logo_url": "http://example.org/logo.png"},
        {"logo_url": "javascript:alert(1)"},
        {"logo_url": "data:image/png;base64,AAAA"},
        {"logo_url": "https://"},
        {"logo_url": "https://example.org/a b.png"},
        {"logo_url": "https://example.org/" + "a" * 500},
        {"logo_url": 5},
    ],
)
def test_set_branding_refuses_bad_values(changes):
    from modules.organizations import service

    org, db = make_org({"branding": {"accent_color": "#000000"}}), FakeDB()
    with pytest.raises(service.BrandingError) as error:
        service.set_branding(db, org, changes)
    assert error.value.status == 400
    assert org.config == {"branding": {"accent_color": "#000000"}}
    assert db.commits == 0


def test_officer_sets_branding_and_overview_shows_it(client, officer_headers, restore_soda_config):
    path = "/api/dashboard/soda/branding"
    assert client.get(path, headers=officer_headers).get_json() == {"logo_url": None, "accent_color": None}

    refused = client.put(path, json={"accent_color": "blue"}, headers=officer_headers)
    assert refused.status_code == 400
    assert "accent_color" in refused.get_json()["error"]
    assert client.put(path, json={"logo_url": "http://x.org/a.png"}, headers=officer_headers).status_code == 400

    body = {"logo_url": "https://example.org/logo.svg", "accent_color": "#AA3300"}
    saved = client.put(path, json=body, headers=officer_headers)
    assert saved.status_code == 200
    assert saved.get_json() == {"logo_url": "https://example.org/logo.svg", "accent_color": "#aa3300"}
    assert client.get(path, headers=officer_headers).get_json() == saved.get_json()

    overview = client.get("/api/dashboard/soda/overview", headers=officer_headers).get_json()
    assert overview["organization"]["branding"] == saved.get_json()


def test_branding_write_is_audited(client, officer_headers, restore_soda_config):
    from core.audit import AuditEntry
    from shared import db_connect

    db = db_connect.SessionLocal()
    start = db.query(AuditEntry.id).order_by(AuditEntry.id.desc()).limit(1).scalar() or 0
    db.close()
    client.put("/api/dashboard/soda/branding", json={"accent_color": "#123456"}, headers=officer_headers)
    db = db_connect.SessionLocal()
    rows = db.query(AuditEntry).filter(AuditEntry.id > start).all()
    db.close()
    assert [(r.action, r.org, r.actor_id, r.status) for r in rows] == [
        ("PUT /api/dashboard/<string:org_prefix>/branding", "soda", OFFICER_DISCORD_ID, 200)
    ]


class TestPermissions:
    @pytest.fixture(autouse=True)
    def enforce(self, app, monkeypatch, restore_soda_config):
        from modules.auth import access
        from shared import config

        access.clear_cache()
        monkeypatch.setattr(app, "discord_directory", ScopedBot())
        monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
        monkeypatch.setattr(config, "ACCESS_ENFORCE", True)
        yield
        access.clear_cache()

    def test_signed_out_is_refused(self, client):
        assert client.get("/api/dashboard/soda/branding").status_code == 401
        assert client.put("/api/dashboard/soda/branding", json={"accent_color": "#000000"}).status_code == 401

    @pytest.mark.parametrize("method", ["GET", "PUT"])
    def test_other_orgs_officer_is_refused(self, client, method):
        response = client.open(
            "/api/dashboard/soda/branding",
            method=method,
            json={"accent_color": "#000000"},
            headers=headers_for(AIS_OFFICER_ID),
        )
        assert response.status_code == 403

    def test_own_officer_and_superadmin_may_write(self, client):
        for discord_id in (OFFICER_DISCORD_ID, SUPERADMIN_ID):
            response = client.put(
                "/api/dashboard/soda/branding", json={"accent_color": "#0a0a0a"}, headers=headers_for(discord_id)
            )
            assert response.status_code == 200

    def test_unknown_org_is_404(self, client):
        response = client.get("/api/dashboard/nope/branding", headers=headers_for(SUPERADMIN_ID))
        assert response.status_code == 404
