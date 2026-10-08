"""Orgs save their own integration tokens, encrypted; the API never returns them."""

import json
from typing import cast

import pytest
from cryptography.fernet import Fernet

TOKEN = "secret_notion_token_123"


@pytest.fixture
def soda_id(client, officer_headers):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


@pytest.fixture
def key(monkeypatch, client, officer_headers, soda_id):
    value = Fernet.generate_key().decode()
    monkeypatch.setenv("SECRETS_KEY", value)
    yield value
    for name in ("notion_api_key", "google_service_account"):
        client.delete(f"/api/organizations/{soda_id}/secrets/{name}", headers=officer_headers)


def _put(client, headers, org_id, value=TOKEN, name="notion_api_key"):
    return client.put(f"/api/organizations/{org_id}/secrets/{name}", json={"value": value}, headers=headers)


def test_saved_secret_is_encrypted_and_never_returned(client, officer_headers, soda_id, key):
    assert _put(client, officer_headers, soda_id).status_code == 200
    listing = client.get(f"/api/organizations/{soda_id}/secrets", headers=officer_headers)
    assert listing.status_code == 200
    assert TOKEN not in listing.get_data(as_text=True)
    [entry] = [s for s in listing.get_json()["secrets"] if s["name"] == "notion_api_key"]
    assert entry["set"] is True

    from core import secrets
    from core.secrets import OrgSecret
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        assert TOKEN not in db.query(OrgSecret).filter_by(organization_id=soda_id).one().ciphertext
        assert secrets.get_secret(db, soda_id, "notion_api_key") == TOKEN
    finally:
        db.close()


def test_key_rotation_keeps_old_secrets_readable(client, officer_headers, soda_id, key, monkeypatch):
    _put(client, officer_headers, soda_id)
    monkeypatch.setenv("SECRETS_KEY", f"{Fernet.generate_key().decode()},{key}")
    from core import secrets
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        assert secrets.get_secret(db, soda_id, "notion_api_key") == TOKEN
    finally:
        db.close()


def test_calendar_uses_the_orgs_own_notion_token(client, officer_headers, soda_id, key, monkeypatch):
    from modules.calendar import service
    from modules.calendar.clients import NotionCalendarClient
    from modules.organizations.models import Organization
    from shared import db_connect

    _put(client, officer_headers, soda_id)
    db_session = db_connect.SessionLocal()
    try:
        org = db_session.query(Organization).filter_by(prefix="soda").one()
        notion = service.get_service().notion_for(db_session, org)
    finally:
        db_session.close()
    assert isinstance(notion, NotionCalendarClient)
    assert notion is not service.get_service().notion_client
    assert notion.notion.options.auth == TOKEN


@pytest.mark.parametrize("name,value", [("unknown_secret", TOKEN), ("notion_api_key", ""), ("notion_api_key", None)])
def test_bad_secrets_are_refused(client, officer_headers, soda_id, key, name, value):
    assert _put(client, officer_headers, soda_id, value=value, name=name).status_code == 400


def test_saving_without_a_key_is_refused(client, officer_headers, soda_id, monkeypatch):
    monkeypatch.delenv("SECRETS_KEY", raising=False)
    response = _put(client, officer_headers, soda_id)
    assert response.status_code == 400
    assert "SECRETS_KEY" in response.get_json()["error"]


def test_secrets_need_an_officer(client, soda_id):
    assert client.get(f"/api/organizations/{soda_id}/secrets").status_code == 401


def _gcal_for_soda():
    from modules.calendar import service
    from modules.organizations.models import Organization
    from shared import db_connect

    db_session = db_connect.SessionLocal()
    try:
        org = db_session.query(Organization).filter_by(prefix="soda").one()
        return service.get_service().gcal_for(db_session, org)
    finally:
        db_session.close()


def test_calendar_uses_the_instance_google_account_without_an_org_key(client, officer_headers, soda_id, key):
    from modules.calendar import service

    assert _gcal_for_soda() is service.get_service().gcal_client


def test_calendar_uses_the_orgs_own_google_account(client, officer_headers, soda_id, key):
    from modules.calendar import service

    account = {"type": "service_account", "client_email": "cal@soda.iam.gserviceaccount.com"}
    assert (
        _put(client, officer_headers, soda_id, value=json.dumps(account), name="google_service_account").status_code
        == 200
    )
    gcal = _gcal_for_soda()
    assert gcal is not service.get_service().gcal_client
    assert gcal.service_account_info == account


def test_a_broken_org_google_key_fails_instead_of_using_the_instance_account(
    client, officer_headers, soda_id, key, monkeypatch
):
    from shared import config

    monkeypatch.setattr(config, "GOOGLE_SERVICE_ACCOUNT", {"type": "service_account"})
    assert _put(client, officer_headers, soda_id, value="not json", name="google_service_account").status_code == 200
    gcal = _gcal_for_soda()
    assert gcal.service_account_info == {}
    assert gcal.get_service() is None


def test_calendar_update_writes_through_the_given_client(client):
    from modules.calendar import service
    from modules.calendar.clients import GoogleCalendarClient
    from modules.calendar.models import CalendarEventDTO

    class FakeGcal:
        def __init__(self):
            self.created = []

        def get_all_events(self, calendar_id, time_min=None, parent_transaction=None):
            return []

        def create_event(self, calendar_id, data, notion_page_id, parent_transaction=None):
            self.created.append((calendar_id, notion_page_id))
            return "evt1", "https://calendar/evt1"

    fake = FakeGcal()
    event = CalendarEventDTO(
        summary="Meeting", start={"date": "2026-10-09"}, end={"date": "2026-10-09"}, notion_page_id="p1"
    )
    from sentry_sdk import start_transaction

    with start_transaction(op="test", name="update") as transaction:
        results = service.get_service().update_organization_google_calendar(
            [event], "cal1", "db1", transaction, gcal=cast(GoogleCalendarClient, fake)
        )
    assert fake.created == [("cal1", "p1")]
    assert results[0]["status"] == "created"
