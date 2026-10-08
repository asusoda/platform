---
name: new-module
description: Add a feature module under modules/ with its service, routes, models, jobs, tools, migration, tests and docs registered in every place the platform looks. Use when adding a module or a large feature to an existing one.
---

Read `docs/writing-a-module.md` first; it is the source of truth. Copy the shape of `modules/alerts/` (officer routes) or `modules/runpod/` (machine-token routes).

Steps:

1. `modules/<name>/service.py`: logic only. Takes a session and plain values, never imports Flask, raises a subclass of `core.errors.ServiceError(message, status)`. Declare machine token scopes with `modules.auth.scopes.declare` and org secrets with `core.secrets.declare` or `declare_prefix` at the top.
2. `models.py`: tables on `core.db.Base`, `organization_id` on every org-owned row, a unique constraint on the natural key.
3. `api.py`: a blueprint. Use `officer_route` or `machine_route` from `modules/auth/routes.py` with `functools.partial`. Views return a dict or `(dict, status)`.
4. `jobs.py` with `@job` from `core/jobs.py` for scheduled or background work. Import the service inside the function.
5. `tools.py` with `@tool` from `core/tools.py` when agents call the module. No try/except: `ServiceError` becomes a tool error.
6. Register: `MOUNTS` in `modules/registry.py`; `MODEL_MODULES`, `JOB_MODULES`, `TOOL_MODULES` in `modules/manifest.py`; `OPTIONAL_MODULES` in `modules/organizations/service.py` if orgs can switch it off; the Flask-free files in the import-linter contract in `pyproject.toml`.
7. Migration: see the `migration` skill.
8. Tests in `tests/contract/test_<name>.py`. Fake every network call by monkeypatching the module's fetch or client function. Add the module to the expected list in `tests/contract/test_modules.py` when it is switchable.
9. Docs: `modules/<name>/README.md` in the same sections as the others, `docs/<name>.md`, a row in `docs/README.md`, `modules/README.md`, the README module table, the active modules line in `CLAUDE.md`, and the page in `site/scripts/sync-docs.mjs`.
10. Run the `check` skill.

Comments and docs are plain and monotone: what the code does, no justification, no marketing words.
