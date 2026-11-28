"""Helpers for the migration tests: run alembic on a database URL, and the database_url fixture in conftest.py."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def alembic(url: str, *args: str) -> None:
    """Run alembic with args against url, and fail with its stderr."""
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def postgres_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL") or ""
    return url if url.startswith("postgresql") else None
