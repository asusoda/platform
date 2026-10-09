"""Route inventory guard.

Compares every rule in the Flask URL map (path, methods, endpoint) with tests/contract/routes.txt.
A refactor that moves code must leave the file unchanged. To record an intended route change,
run UPDATE_ROUTES=1 uv run pytest tests/contract/test_routes.py and name the change in the PR.
"""

import os
from pathlib import Path

ROUTES = Path(__file__).with_name("routes.txt")


def _inventory(app) -> str:
    rows = sorted(
        f"{rule.rule} {','.join(sorted(rule.methods or ()))} {rule.endpoint}" for rule in app.url_map.iter_rules()
    )
    return "\n".join(rows) + "\n"


def test_route_inventory(app):
    actual = _inventory(app)
    if os.environ.get("UPDATE_ROUTES") == "1":
        ROUTES.write_text(actual)
    assert ROUTES.exists(), "No routes.txt. Run UPDATE_ROUTES=1 uv run pytest tests/contract/test_routes.py"
    assert actual == ROUTES.read_text()
