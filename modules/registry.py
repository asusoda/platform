"""Every module's blueprint, where it is mounted, and which optional module gates it.

To add a module: give it an api.py with a blueprint, add it here, and if orgs should be
able to turn it off, add its name to OPTIONAL_MODULES in modules/organizations/service.py.
"""

import importlib
from dataclasses import dataclass, field

from flask import Blueprint, Flask, jsonify, request

from modules.auth.api import auth_blueprint
from modules.calendar.api import calendar_blueprint
from modules.games.api import game_blueprint
from modules.organizations import service as organizations
from modules.organizations.api import organizations_blueprint
from modules.points.api import points_blueprint
from modules.public.api import public_blueprint
from modules.storefront.api import storefront_blueprint
from modules.superadmin.api import superadmin_blueprint
from modules.users.api import users_blueprint


@dataclass(frozen=True)
class Mount:
    blueprint: Blueprint
    url_prefix: str
    # Optional module that gates every org-scoped route of this blueprint.
    module: str | None = None
    # Optional modules that gate single endpoints, for blueprints that mix features.
    endpoint_modules: dict[str, str] = field(default_factory=dict)


MOUNTS = [
    Mount(public_blueprint, "/api/public", endpoint_modules={"get_leaderboard": "points"}),
    Mount(points_blueprint, "/api/points", module="points"),
    Mount(users_blueprint, "/api/users"),
    Mount(auth_blueprint, "/api/auth"),
    Mount(calendar_blueprint, "/api/calendar", module="calendar"),
    Mount(game_blueprint, "/api/bot"),
    Mount(organizations_blueprint, "/api/organizations"),
    Mount(superadmin_blueprint, "/api/superadmin"),
    Mount(storefront_blueprint, "/api/storefront", module="storefront"),
]


# Modules with background jobs. Importing a jobs.py registers its jobs with core.jobs.
JOB_MODULES = ["core.audit", "modules.auth.jobs", "modules.points.jobs", "modules.calendar.jobs"]


def load_jobs() -> None:
    for name in JOB_MODULES:
        importlib.import_module(name)


def _gate(mount: Mount):
    def check_module_enabled():
        org_prefix = (request.view_args or {}).get("org_prefix")
        endpoint = (request.endpoint or "").rpartition(".")[2]
        module = mount.endpoint_modules.get(endpoint, mount.module)
        if not org_prefix or not module:
            return None
        from shared import db_connect

        db = db_connect.SessionLocal()
        try:
            org = organizations.find_by_prefix(db, org_prefix)
            if org is not None and not organizations.module_enabled(org, module):
                return jsonify({"error": f"The {module} module is turned off for this organization"}), 404
        finally:
            db.close()
        return None

    return check_module_enabled


def register_modules(app: Flask) -> None:
    for mount in MOUNTS:
        if mount.module or mount.endpoint_modules:
            mount.blueprint.before_request(_gate(mount))
        app.register_blueprint(mount.blueprint, url_prefix=mount.url_prefix)
