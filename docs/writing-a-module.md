# Writing a module

Every feature lives in one folder under `modules/`. This page lists the files a module can have,
where it is registered, and the rules `make ci` checks.

## Files

| File | Holds | Needed |
| --- | --- | --- |
| `README.md` | What the module does, its files, routes, jobs, tools and tables | always |
| `service.py` | The logic. Takes a DB session and plain values, returns plain values, raises `ServiceError`. Does not import Flask | when the module does more than read a table |
| `api.py` | A Flask blueprint. Each route reads the request, calls `service.py` and returns JSON | when the module has HTTP routes |
| `models.py` | SQLAlchemy tables, each a subclass of `core.base.Base` | when the module stores data |
| `jobs.py` | Background work declared with `@job` from `core/jobs.py` | when the module runs on a schedule or in the background |
| `tools.py` | Tools for agents declared with `@tool` from `core/tools.py`. Served over MCP and `/api/tools` | when agents call the module |

A module that grows past one concern splits `service.py` into more Flask-free files
(`compute/` has `ssh.py`, `files.py`, `schedule.py`). Add each one to the Flask contract below.

## Registering it

| What | Where |
| --- | --- |
| Blueprint and URL prefix | `MOUNTS` in `modules/registry.py` |
| Org switch, so an org can turn it off | `OPTIONAL_MODULES` in `modules/organizations/service.py`, and `module=` on its `Mount` |
| Jobs | `JOB_MODULES` in `modules/registry.py` |
| Tools | `TOOL_MODULES` in `modules/registry.py` |
| Tables | the model list in `alembic/env.py`, then `uv run alembic revision --autogenerate -m "..."` |
| Machine token scopes | `scopes.declare(...)` from `modules/auth/scopes.py`, at the top of `service.py` |
| Flask-free files | the "service modules do not import Flask" contract in `pyproject.toml` |
| Docs | a page in `docs/`, listed in `docs/README.md` and in `site/scripts/sync-docs.mjs` |

## Routes

Routes for people use the decorators in `modules/auth/decoraters.py` (`member_required`,
`org_officer_required`, `superadmin_required` and others). Officer routes under an org prefix can use `officer_route`, and routes for apps and agents use
`machine_route`, both from `modules/auth/routes.py`:

```python
from functools import partial

from flask import Blueprint

from modules.auth.routes import json_body, machine_route

from . import service

things_blueprint = Blueprint("things", __name__)
_route = partial(machine_route, things_blueprint)


@_route("/things/<string:key>", "things:write", ["PUT"])
def put_thing(db, org, key):
    return service.put_thing(db, int(org.id), key, json_body()), 201
```

`machine_route` checks the token and its scope, opens a session, loads the token's organization,
and turns a `ServiceError` into `{"error": message}` with the error's status. The view returns a
dict or a `(dict, status)` tuple.

## Errors

A module defines one error class that subclasses `core.errors.ServiceError`:

```python
class ThingError(ServiceError):
    pass


raise ThingError("No thing with that key", 404)
```

Routes built on `machine_route` and every tool answer with its message and status, so a tool
function calls the service directly and needs no `try`.

## Rules checked by `make ci`

- `core/` imports nothing from `modules/` (import-linter).
- Files in the Flask contract do not import Flask (import-linter).
- ruff lint and format, ty type check, bandit.
- `tests/contract/` checks every route a client depends on. A new route gets a test there.

## Example to copy

`modules/runpod/` is a small module with every file: `service.py`, `api.py` on `machine_route`,
`models.py`, `jobs.py` and `tools.py`.
