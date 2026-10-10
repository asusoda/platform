"""Settings moved from .env to the dashboard: the default pod image and knowledge publishers."""

from tests.contract.test_access import SUPERADMIN_ID, headers_for

SETTINGS = "/api/compute/ais/settings"


def test_default_pod_image(client, officer_headers):
    from core.config import config

    got = client.get(SETTINGS, headers=officer_headers).get_json()["settings"]
    assert got == {"pod_image": None, "deployment_pod_image": config.COMPUTE_POD_IMAGE}
    saved = client.put(SETTINGS, json={"pod_image": "org/image:1"}, headers=officer_headers)
    assert saved.get_json()["settings"]["pod_image"] == "org/image:1"
    for bad in ({"pod_image": "a b"}, {"pod_image": 3}, {"other": 1}, ["x"]):
        assert client.put(SETTINGS, json=bad, headers=officer_headers).status_code == 400, bad
    reset = client.put(SETTINGS, json={"pod_image": None}, headers=officer_headers)
    assert reset.get_json()["settings"]["pod_image"] is None


def test_superadmin_marks_publishers(client, monkeypatch):
    from core.config import config
    from core.db import db_connect
    from modules.knowledge import service
    from modules.organizations.models import Organization

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setattr(config, "ACCESS_ENFORCE", True)
    monkeypatch.setenv("KNOWLEDGE_PUBLISHERS", "soda")
    db = db_connect.SessionLocal()
    try:
        ais = db.query(Organization).filter_by(prefix="ais").one().id
    finally:
        db.close()
    path = f"/api/superadmin/publishers/{ais}"
    assert client.put(path, json={"publisher": True}, headers=headers_for("900000000000000003")).status_code == 403
    assert client.put(path, json={"publisher": "yes"}, headers=headers_for(SUPERADMIN_ID)).status_code == 400
    on = client.put(path, json={"publisher": True}, headers=headers_for(SUPERADMIN_ID)).get_json()["publishers"]
    assert {(p["prefix"], p["source"]) for p in on} == {("soda", "env"), ("ais", "superadmin")}
    db = db_connect.SessionLocal()
    try:
        assert service.can_publish(db, "ais")
    finally:
        db.close()
    off = client.put(path, json={"publisher": False}, headers=headers_for(SUPERADMIN_ID)).get_json()["publishers"]
    assert [p["prefix"] for p in off] == ["soda"]
