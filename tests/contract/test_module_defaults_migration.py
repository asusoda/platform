"""The migration that turns off compute, alerts and uptime for existing orgs that have no data for them."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BEFORE = "2eb2a9096622"
AFTER = "c4d6e8f0a2b4"


def _alembic(db_path, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def _modules(db, org_id):
    (config,) = db.execute("SELECT config FROM organizations WHERE id = ?", (org_id,)).fetchone()
    return (json.loads(config) if config else {}).get("modules")


def test_unused_new_modules_turn_off_and_used_or_set_ones_stay(tmp_path):
    db_path = tmp_path / "orgs.db"
    _alembic(db_path, "upgrade", BEFORE)
    db = sqlite3.connect(db_path)
    orgs = [
        (1, "SoDA", "soda", "1", None),
        (2, "AIS", "ais", "2", json.dumps({"modules": {"points": False}})),
        (3, "Club", "club", "3", json.dumps({"modules": {"alerts": True}})),
    ]
    db.executemany(
        "INSERT INTO organizations (id, name, prefix, guild_id, is_active, config) VALUES (?, ?, ?, ?, 1, ?)", orgs
    )
    db.execute(
        "INSERT INTO compute_pods (id, organization_id, pod_id, provider, name, is_public, allowed_users, config, "
        "created_at) VALUES ('p1', 2, 'pod1', 'runpod', 'pod', 0, '[]', '{}', '2026-10-09')"
    )
    db.commit()
    db.close()

    _alembic(db_path, "upgrade", AFTER)
    db = sqlite3.connect(db_path)
    assert _modules(db, 1) == {"compute": False, "alerts": False, "uptime": False}
    assert _modules(db, 2) == {"points": False, "alerts": False, "uptime": False}
    assert _modules(db, 3) == {"alerts": True, "compute": False, "uptime": False}
    db.close()
