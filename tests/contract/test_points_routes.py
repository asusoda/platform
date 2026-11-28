"""Status codes and bodies of the points officer routes, kept the same when their logic moved to service.py."""

import pytest

from tests.contract.conftest import MEMBER_DISCORD_ID, MEMBER_EMAIL

EVENT = "Route test"


@pytest.fixture
def remove_route_entries(app):
    yield
    from core.db import db_connect
    from modules.points.models import Points

    with db_connect.SessionLocal() as db:
        db.query(Points).filter(Points.event == EVENT).delete()
        db.commit()


def _post(client, headers, path, body):
    response = client.post(path, json=body, headers=headers)
    return response.status_code, response.get_json()


def test_add_points(client, officer_headers, remove_route_entries):
    path = "/api/points/soda/add_points"
    status, body = _post(
        client, officer_headers, path, {"user_discord_id": MEMBER_DISCORD_ID, "points": 3, "event": EVENT}
    )
    assert status == 201
    assert (body["points"], body["event"], body["organization_id"]) == (3, EVENT, 1)
    status, body = _post(client, officer_headers, path, {"user_identifier": MEMBER_EMAIL, "points": 2, "event": EVENT})
    assert (status, body["points"]) == (201, 2)

    assert _post(client, officer_headers, path, {"points": 1}) == (
        400,
        {"error": "Either 'user_discord_id' or 'user_identifier' must be provided"},
    )
    assert _post(client, officer_headers, path, {"user_identifier": "nobody@asu.edu", "points": 1}) == (
        404,
        {"error": "User does not exist"},
    )
    assert _post(client, officer_headers, "/api/points/nope/add_points", {"user_identifier": MEMBER_EMAIL}) == (
        400,
        {"error": "Organization not found"},
    )
    status, _ = _post(client, officer_headers, path, {"user_identifier": MEMBER_EMAIL})
    assert status == 400


def test_assign_points_refusals(client, officer_headers, remove_route_entries):
    path = "/api/points/soda/assign_points"
    assert _post(client, officer_headers, path, {"points": 1}) == (400, {"error": "user_identifier is required"})
    assert _post(client, officer_headers, path, {"user_identifier": MEMBER_EMAIL}) == (
        400,
        {"error": "points is required"},
    )
    assert _post(client, officer_headers, path, {"user_identifier": "nobody@asu.edu", "points": 1}) == (
        404,
        {"error": "User not found"},
    )
    assert _post(client, officer_headers, "/api/points/nope/assign_points", {}) == (
        404,
        {"error": "Organization not found"},
    )


def test_delete_points_by_event(client, officer_headers, remove_route_entries):
    path = "/api/points/soda/delete_points"
    _post(
        client,
        officer_headers,
        "/api/points/soda/add_points",
        {"user_identifier": MEMBER_EMAIL, "points": 4, "event": EVENT},
    )

    response = client.delete(path, json={"user_email": MEMBER_EMAIL, "event": EVENT}, headers=officer_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["message"] == "Points deleted successfully"
    assert (body["deleted_points"]["points"], body["deleted_points"]["event"]) == (4, EVENT)

    again = client.delete(path, json={"user_email": MEMBER_EMAIL, "event": EVENT}, headers=officer_headers)
    assert (again.status_code, again.get_json()) == (404, {"error": "Points entry not found"})
    nobody = client.delete(path, json={"user_email": "nobody@asu.edu", "event": EVENT}, headers=officer_headers)
    assert (nobody.status_code, nobody.get_json()) == (404, {"error": "User not found"})
    missing = client.delete(path, json={"event": EVENT}, headers=officer_headers)
    assert (missing.status_code, missing.get_json()) == (400, {"error": "user_email and event are required"})


def test_member_points_refusals(client, officer_headers):
    response = client.get("/api/points/soda/users/nobody@asu.edu/points", headers=officer_headers)
    assert (response.status_code, response.get_json()) == (404, {"error": "User not found"})
    response = client.get(f"/api/points/nope/users/{MEMBER_EMAIL}/points", headers=officer_headers)
    assert (response.status_code, response.get_json()) == (404, {"error": "Organization not found"})


def test_update_member_fields(client, officer_headers):
    path = f"/api/points/soda/users/{MEMBER_EMAIL}"
    response = client.put(path, json={}, headers=officer_headers)
    assert (response.status_code, response.get_json()) == (200, {"message": "No fields to update"})
    response = client.put("/api/points/soda/users/nobody@asu.edu", json={"name": "X"}, headers=officer_headers)
    assert response.status_code == 404


def test_save_member_refusal_and_unknown_org(client, officer_headers):
    response = client.post("/api/points/nope/users", json={"email": "x@asu.edu"}, headers=officer_headers)
    assert (response.status_code, response.get_json()) == (404, {"error": "Organization not found"})


def test_officer_lists(client, officer_headers):
    users = client.get("/api/points/soda/users", headers=officer_headers)
    assert users.status_code == 200
    assert {"organization", "total_users", "users"} <= set(users.get_json())
    entries = client.get("/api/points/soda/get_points", headers=officer_headers)
    assert entries.status_code == 200
    ids = [row["id"] for row in entries.get_json()]
    assert ids == sorted(ids)
    for path in ("/api/points/nope/users", "/api/points/nope/get_points"):
        response = client.get(path, headers=officer_headers)
        assert (response.status_code, response.get_json()) == (404, {"error": "Organization not found"})


def test_upload_event_csv_refusals(client, officer_headers):
    import io

    path = "/api/points/soda/uploadEventCSV"

    def upload(name, data, points="5"):
        form = {"file": (io.BytesIO(data), name), "event_name": EVENT, "event_points": points}
        response = client.post(path, data=form, headers=officer_headers, content_type="multipart/form-data")
        return response.status_code, response.get_json()

    assert upload("a.csv", b"x", points="five") == (400, {"error": "event_points must be a whole number"})
    assert upload("a.txt", b"x") == (400, {"error": "File must be a CSV"})
    assert upload("a.csv", b"\xff\xfe\xfa") == (400, {"error": "The CSV must be UTF-8 text"})
    assert upload("a.csv", b"x" * 2_000_001) == (413, {"error": "The CSV is larger than 2 MB"})
    response = client.post(path, data={"event_name": EVENT}, headers=officer_headers)
    assert (response.status_code, response.get_json()) == (400, {"error": "Missing required fields"})
