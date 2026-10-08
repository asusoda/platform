# Writing a module

This page lists the files a module can have, the places to register it, and the rules that `make ci` checks. The `new-module` skill in `.agents/skills/` has the full procedure.

## Files

| File | Holds | Add it when |
| --- | --- | --- |
| `README.md` | What the module does, a Files table and a Surface list (routes, jobs, tools, tables) | always |
| `service.py` | The logic. It takes a database session and plain values, returns plain values and raises a `ServiceError`. It does not import Flask | the module does more than read a table |
| `api.py` | A Flask blueprint. Each route reads the request, calls `service.py` and returns JSON | the module has routes |
| `models.py` | SQLAlchemy tables that use `Base` from `core/db/base.py` | the module keeps data |
| `jobs.py` | Background work with `@job` from `core/jobs.py` | the module runs on a schedule or in the background |
| `tools.py` | Tools for agents with `@tool` from `core/tools.py` | agents call the module |

If `service.py` has more than one concern, split it into more Flask-free files. For example, `compute/` has `ssh.py`, `files.py` and `schedule.py`.

## Register it

| What | Where |
| --- | --- |
| Blueprint and URL prefix | `MOUNTS` in `modules/registry.py` |
| Org switch | `OPTIONAL_MODULES` in `modules/organizations/service.py`, and `module=` on the `Mount` |
| Tables | `MODEL_MODULES` in `modules/manifest.py`, then `uv run alembic revision --autogenerate -m "..."` |
| Jobs | `JOB_MODULES` in `modules/manifest.py` |
| Tools | `TOOL_MODULES` in `modules/manifest.py` |
| Machine token scopes | `scopes.declare(...)` from `modules/auth/scopes.py`, at the top of `service.py` |
| Org secrets | `secrets.declare(...)` from `core/secrets.py` |
| Flask-free files | The "service modules do not import Flask" contract in `pyproject.toml` |
| Routes | `tests/contract/routes.txt`: run `UPDATE_ROUTES=1 uv run pytest tests/contract/test_routes.py` |
| Docs | The module `README.md`, a row in `modules/README.md`, and the active modules line in `AGENTS.md` and `CLAUDE.md` |

If the module needs more than its README, add `docs/modules/<name>.md`, a row in `docs/README.md`, and the page in `site/scripts/sync-docs.mjs`.

## Routes

Use the helpers in `modules/auth/routes.py`. Each one checks the caller, opens a database session, finds the org and changes a `ServiceError` into `{"error": message}` with its status.

| Helper | Use it for | The view gets |
| --- | --- | --- |
| `officer_route(blueprint, rule, methods)` | Officer routes under `/<org_prefix>` | `db, org, **path args` |
| `machine_route(blueprint, rule, scope, methods)` | Routes for apps and agents with a machine token | `db, org, **path args` |
| `member_view(view)` | Routes for members signed in with Discord | `db, org, discord_id, **path args` |

```python
from functools import partial

from flask import Blueprint

from core.http.responses import json_body
from modules.auth.routes import machine_route

from . import service

things_blueprint = Blueprint("things", __name__)
_route = partial(machine_route, things_blueprint)


@_route("/things/<string:key>", "things:write", ["PUT"])
def put_thing(db, org, key):
    return service.put_thing(db, int(org.id), key, json_body()), 201
```

A view returns a dict, or a `(dict, status)` tuple. For other routes, use the decorators in `modules/auth/decorators.py`. See [Authentication](./authentication.md).

## Errors

A module has one error class, a subclass of `core.errors.ServiceError`:

```python
class ThingError(ServiceError):
    pass


raise ThingError("No thing with that key", 404)
```

The route helpers and the tool runner return its message and status. A tool function thus calls the service and needs no `try`.

## Rules that `make ci` checks

- `core/` imports nothing from `modules/` (import-linter).
- The files in the Flask-free contract do not import Flask (import-linter).
- ruff lint and format, and the ty type check. CI also runs bandit.
- `tests/contract/routes.txt` agrees with the routes of the app.
- `tests/contract/` checks each route that a client uses. Add a test there for a new route.
- `alembic check` finds no model change without a migration.

## Example

`modules/runpod/` is a small module with every file: `service.py`, `api.py` on `machine_route`, `models.py`, `jobs.py` and `tools.py`. `modules/alerts/` is the example for `officer_route`.
