"""The migration that drops agent memory and member linked accounts."""

import json
import sqlite3

from .test_module_rename_migration import _alembic, _config, _scopes

BEFORE = "d5f9b2e7a1c3"
AFTER = "f2a4c6e8b0d1"
NOW = "2026-11-28 00:00:00"
TABLES = ("agent_conversations", "agent_memories", "agent_messages", "account_grants", "account_logins")


def _tables(db) -> set[str]:
    return {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _token(db, token_id, scopes):
    db.execute(
        "INSERT INTO machine_tokens (id, organization_id, name, kind, scopes, token_hash, display, created_at) "
        "VALUES (?, 1, 'agent', 'agent', ?, ?, 'plat_', ?)",
        (token_id, json.dumps(scopes), f"h{token_id}", NOW),
    )


def test_tables_modules_scopes_and_limits_go(tmp_path):
    db_path = tmp_path / "agents.db"
    _alembic(db_path, "upgrade", BEFORE)
    db = sqlite3.connect(db_path)
    config = {"modules": {"agents": True, "accounts": True, "points": True}}
    db.execute(
        "INSERT INTO organizations (id, name, prefix, guild_id, is_active, config) VALUES (1, 'AIS', 'ais', '1', 1, ?)",
        (json.dumps(config),),
    )
    db.execute(
        "INSERT INTO org_limits (organization_id, key, value, updated_at) VALUES (1, 'agents.memories', 5, ?)", (NOW,)
    )
    db.execute(
        "INSERT INTO org_limits (organization_id, key, value, updated_at) VALUES (1, 'knowledge.pages', 9, ?)", (NOW,)
    )
    _token(db, 1, ["agents:read", "knowledge:read"])
    _token(db, 2, ["agents:write", "accounts:token"])
    db.execute(
        "INSERT INTO oauth_clients (id, client_id, info, created_at, last_used_at) VALUES (1, 'c', '{}', ?, ?)",
        (NOW, NOW),
    )
    db.execute(
        "INSERT INTO oauth_grants (id, machine_token_id, client_id, refresh_hash, refresh_expires_at, checked_at, "
        "created_at, scopes) VALUES (1, 1, 'c', 'r', ?, ?, ?, ?)",
        (NOW, NOW, NOW, json.dumps(["agents:read", "knowledge:read"])),
    )
    db.commit()
    db.close()

    _alembic(db_path, "upgrade", AFTER)
    db = sqlite3.connect(db_path)
    assert not _tables(db) & set(TABLES)
    assert _config(db, 1) == {"modules": {"points": True}}
    assert db.execute("SELECT key FROM org_limits").fetchall() == [("knowledge.pages",)]
    assert _scopes(db, 1) == ["knowledge:read"]
    assert db.execute("SELECT revoked_at FROM machine_tokens WHERE id = 1").fetchone() == (None,)
    # A token left with no scope can do nothing, so the migration revokes it
    assert _scopes(db, 2) == []
    assert db.execute("SELECT revoked_at FROM machine_tokens WHERE id = 2").fetchone()[0] is not None
    (grant,) = db.execute("SELECT scopes FROM oauth_grants WHERE id = 1").fetchone()
    assert json.loads(grant) == ["knowledge:read"]
    db.close()

    _alembic(db_path, "downgrade", BEFORE)
    db = sqlite3.connect(db_path)
    assert _tables(db) >= set(TABLES)
    assert db.execute("SELECT COUNT(*) FROM agent_memories").fetchone() == (0,)
    db.close()
