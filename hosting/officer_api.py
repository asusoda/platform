"""HTTP routes for officers to manage the org's apps, under /api/dashboard/<org_prefix>.

The same services as the machine-token routes in api.py, for officers who sign in to the dashboard.
"""

from functools import partial
from typing import cast

from flask import Blueprint, request

from core import hosting as providers
from core.http.responses import json_body
from modules.auth import access
from modules.auth.routes import officer_route

from . import service, shared, templates

hosting_officer_blueprint = Blueprint("hosting", __name__)
_officer = partial(officer_route, hosting_officer_blueprint)


def _org_id(org) -> int:
    return cast(int, org.id)


def _actor() -> str:
    principal = access.current_principal()
    return f"officer:{principal.discord_id}" if principal and principal.discord_id else "officer"


# Hosting providers and the apps that run on them


@_officer("/hosting/providers", ["GET"])
def hosting_providers(db, org):
    return {"providers": providers.listing(db, _org_id(org))}


@_officer("/apps", ["GET"], module="hosting")
def list_apps(db, org):
    return {"apps": service.list_apps(db, _org_id(org))}


@_officer("/apps/templates", ["GET"], module="hosting")
def list_app_templates(db, org):
    return {"templates": templates.list_templates()}


@_officer("/apps/templates/<string:template>", ["POST"], module="hosting")
def create_app_from_template(db, org, template):
    data = json_body()
    app = templates.create(
        db,
        _org_id(org),
        template,
        data.get("name"),
        data.get("values"),
        data.get("secrets"),
        data.get("provider"),
        _actor(),
    )
    return app, 201


@_officer("/apps/<string:name>", ["GET"], module="hosting")
def get_app(db, org, name):
    return service.get_app(db, _org_id(org), name) | {"deployments": service.deployments(db, _org_id(org), name)}


@_officer("/apps/<string:name>", ["PUT"], module="hosting")
def put_app(db, org, name):
    data = json_body()
    return service.put_app(
        db, _org_id(org), name, data.get("manifest"), data.get("repo"), data.get("manifest_path"), data.get("provider")
    )


@_officer("/apps/<string:name>", ["DELETE"], module="hosting")
def delete_app(db, org, name):
    return service.delete_app(db, _org_id(org), name)


@_officer("/apps/<string:name>/pod", ["GET"], module="hosting")
def get_app_pod(db, org, name):
    return {"pod": service.pod(db, _org_id(org), name)}


@_officer("/apps/<string:name>/action", ["POST"], module="hosting")
def app_action(db, org, name):
    """Start, stop or restart the app. Body: {"action": "restart"}."""
    return service.app_action(db, _org_id(org), name, json_body().get("action"))


@_officer("/apps/<string:name>/logs", ["GET"], module="hosting")
def app_logs(db, org, name):
    return service.app_logs(db, _org_id(org), name, request.args.get("lines", 200, type=int))


@_officer("/apps/<string:name>/deploy", ["POST"], module="hosting")
def deploy_app(db, org, name):
    data = json_body()
    dry_run = data.get("dry_run") is True
    result = service.deploy(
        db, _org_id(org), str(org.prefix), name, data.get("tag"), _actor(), dry_run=dry_run, ref=data.get("ref")
    )
    return result, 200 if dry_run else 202


@_officer("/apps/<string:name>/rollback", ["POST"], module="hosting")
def rollback_app(db, org, name):
    dry_run = json_body().get("dry_run") is True
    result = service.rollback(db, _org_id(org), str(org.prefix), name, _actor(), dry_run=dry_run)
    return result, 200 if dry_run else 202


@_officer("/shared-apps", ["GET"])
def list_shared_apps(db, org):
    """The shared apps the org can subscribe to, and its subscriptions."""
    return {"apps": shared.for_org(db, _org_id(org))}


@_officer("/shared-apps/<string:name>/subscription", ["PUT"])
def subscribe_shared_app(db, org, name):
    """Subscribe the org to a shared app. Body: {"emails": [...]}: the people to give access, such as officers."""
    return shared.subscribe(db, _org_id(org), name, json_body().get("emails"), _actor())


@_officer("/shared-apps/<string:name>/subscription", ["DELETE"])
def unsubscribe_shared_app(db, org, name):
    return shared.unsubscribe(db, _org_id(org), name)
