"""Member id and standing columns: the migration, legacy and neutral request keys, and legacy response keys."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.contract.conftest import MEMBER_EMAIL

ROOT = Path(__file__).resolve().parents[2]
BEFORE = "cfdd092e0a0e"
AFTER = "b7d9f1a3c5e8"
EMAIL = "carol@example.edu"


def _alembic(db_path, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def _columns(db, table):
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def _indexes(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'users'")}


def test_migration_renames_columns_and_keeps_data(tmp_path):
    db_path = tmp_path / "members.db"
    _alembic(db_path, "upgrade", BEFORE)
    db = sqlite3.connect(db_path)
    db.execute("INSERT INTO organizations (id, name, prefix, guild_id, is_active) VALUES (1, 'SoDA', 'soda', '1', 1)")
    db.execute(
        "INSERT INTO users (id, name, email, asu_id, academic_standing, uuid) "
        "VALUES (1, 'A', 'a@x', '120', 'Senior', 'u1')"
    )
    db.execute(
        "INSERT INTO user_organization_memberships (id, user_id, organization_id, is_active) VALUES (1, 1, 1, 1)"
    )
    db.commit()
    db.close()

    _alembic(db_path, "upgrade", AFTER)
    db = sqlite3.connect(db_path)
    assert {"student_id", "class_standing"} <= _columns(db, "users")
    assert not {"asu_id", "academic_standing"} & _columns(db, "users")
    assert "ix_users_student_id" in _indexes(db)
    assert db.execute("SELECT student_id, class_standing FROM users").fetchall() == [("120", "Senior")]
    assert db.execute("SELECT profile_fields FROM user_organization_memberships").fetchall() == [("{}",)]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO users (id, name, student_id, uuid) VALUES (2, 'B', '120', 'u2')")
    db.close()

    _alembic(db_path, "downgrade", BEFORE)
    db = sqlite3.connect(db_path)
    assert {"asu_id", "academic_standing"} <= _columns(db, "users")
    assert "profile_fields" not in _columns(db, "user_organization_memberships")
    assert "ix_users_asu_id" in _indexes(db)
    assert db.execute("SELECT asu_id, academic_standing FROM users").fetchall() == [("120", "Senior")]
    db.close()


@pytest.fixture
def carol(app):
    """Removes the member these tests create, so the shared database matches the contract snapshots."""
    from core.db import db_connect
    from modules.points.models import User, UserOrganizationMembership

    yield EMAIL
    db = db_connect.SessionLocal()
    try:
        user = db.query(User).filter_by(email=EMAIL).first()
        if user:
            db.query(UserOrganizationMembership).filter_by(user_id=user.id).delete()
            db.delete(user)
            db.commit()
    finally:
        db.close()


def _stored(email):
    from core.db import db_connect
    from modules.points.models import User

    db = db_connect.SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).one()
        return user.student_id, user.class_standing
    finally:
        db.close()


def test_legacy_keys_are_accepted_and_returned(client, officer_headers, carol):
    body = {"name": "Carol", "email": carol, "asu_id": "1300000001", "academic_standing": "Junior"}
    response = client.post("/api/points/soda/users", json=body, headers=officer_headers)
    assert response.status_code == 201
    user = response.get_json()["user"]
    assert user["asu_id"] == user["student_id"] == "1300000001"
    assert user["academic_standing"] == user["class_standing"] == "Junior"
    assert _stored(carol) == ("1300000001", "Junior")


def test_neutral_keys_win_over_legacy_keys(client, officer_headers, carol):
    body = {
        "name": "Carol",
        "email": carol,
        "asu_id": "1300000001",
        "student_id": "S-42",
        "academic_standing": "Junior",
        "class_standing": "Graduate",
    }
    assert client.post("/api/points/soda/users", json=body, headers=officer_headers).status_code == 201
    assert _stored(carol) == ("S-42", "Graduate")

    update = {"asu_id": "ignored", "student_id": "S-43", "academic_standing": "Senior"}
    response = client.put(f"/api/points/soda/users/{carol}", json=update, headers=officer_headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert sorted(payload["updated_fields"]) == ["academic_standing", "student_id"]
    assert payload["user"]["asu_id"] == "S-43"
    assert _stored(carol) == ("S-43", "Senior")


def test_users_routes_take_both_key_sets(client, officer_headers, carol):
    body = {"email": carol, "name": "Carol", "asu_id": "1300000002", "academic_standing": "Freshman"}
    assert client.post("/api/users/soda/user", json=body, headers=officer_headers).status_code == 201
    update = {"email": carol, "student_id": "S-7", "class_standing": "Sophomore", "profile_fields": {"major": "CS"}}
    assert client.post("/api/users/soda/user", json=update, headers=officer_headers).status_code == 200

    user = client.get(f"/api/users/soda/user?email={carol}", headers=officer_headers).get_json()
    assert user["asu_id"] == user["student_id"] == "S-7"
    assert user["academic_standing"] == user["class_standing"] == "Sophomore"
    assert user["profile_fields"] == {"major": "CS"}


def test_profile_fields_merge_and_validate(client, officer_headers, carol):
    body = {"name": "Carol", "email": carol, "profile_fields": {"major": "CS", "shirt": "M"}}
    assert client.post("/api/points/soda/users", json=body, headers=officer_headers).status_code == 201

    update = {"profile_fields": {"shirt": None, "year_joined": 2026}}
    response = client.put(f"/api/points/soda/users/{carol}", json=update, headers=officer_headers)
    assert response.get_json()["user"]["profile_fields"] == {"major": "CS", "year_joined": 2026}

    bad = client.put(f"/api/points/soda/users/{carol}", json={"profile_fields": ["x"]}, headers=officer_headers)
    assert bad.status_code == 400


def test_snapshotted_routes_return_only_legacy_keys(client, officer_headers):
    users = client.get("/api/points/soda/users", headers=officer_headers).get_json()["users"]
    alice = next(u for u in users if u["email"] == MEMBER_EMAIL)
    assert alice["asu_id"] == "1200000001"
    assert "academic_standing" in alice
    assert not {"student_id", "class_standing", "profile_fields"} & set(alice)

    leaderboard = client.get("/api/public/soda/leaderboard", headers=officer_headers).get_json()["leaderboard"]
    assert any(entry.get("asu_id") == "1200000001" for entry in leaderboard)


def test_member_login_accepts_student_id(client):
    body = {"name": "Alice", "email": MEMBER_EMAIL, "username": "alice", "student_id": "1200000001"}
    response = client.post("/api/points/soda/member_login", json=body)
    assert response.status_code == 200
    assert response.get_json()["user"]["asu_id"] == "1200000001"
