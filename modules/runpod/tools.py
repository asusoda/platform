"""RunPod app tools."""

from core.tools import tool
from modules.runpod import service


@tool(
    "apps.list",
    description="Apps the organization runs on RunPod: image tag, pod id and the latest deployment's status.",
    scope="apps:read",
)
def apps_list(db, org, caller):
    apps = service.list_apps(db, int(org.id))
    return {"apps": [{k: v for k, v in app.items() if k != "manifest"} for app in apps]}


NAME = {"type": "string", "minLength": 1, "maxLength": 64}


@tool(
    "apps.get",
    description="One app: its manifest, pod, tag and recent deployments.",
    scope="apps:read",
    input_schema={"type": "object", "properties": {"name": NAME}, "required": ["name"], "additionalProperties": False},
)
def apps_get(db, org, caller, name: str):
    return service.get_app(db, int(org.id), name) | {"deployments": service.deployments(db, int(org.id), name)}


@tool(
    "apps.register",
    description="Create an app or replace its manifest. Send a manifest object, or a repo whose manifest file is read.",
    scope="apps:manage",
    input_schema={
        "type": "object",
        "properties": {
            "name": NAME,
            "manifest": {"type": "object"},
            "repo": {"type": "string", "maxLength": 200},
            "manifest_path": {"type": "string", "maxLength": 200},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)
def apps_register(db, org, caller, name: str, manifest=None, repo=None, manifest_path=None):
    return service.put_app(db, int(org.id), name, manifest, repo, manifest_path)


@tool(
    "apps.delete",
    description="Forget an app. Its pod keeps running until it is terminated in RunPod.",
    scope="apps:manage",
    confirm=True,
    input_schema={"type": "object", "properties": {"name": NAME}, "required": ["name"], "additionalProperties": False},
)
def apps_delete(db, org, caller, name: str):
    return service.delete_app(db, int(org.id), name)


def _deploy_preview(db, org, caller, name: str, tag: str, ref: str | None = None):
    return service.deploy(db, int(org.id), str(org.prefix), name, tag, caller.actor, dry_run=True, ref=ref)


def _rollback_preview(db, org, caller, name: str):
    return service.rollback(db, int(org.id), str(org.prefix), name, caller.actor, dry_run=True)


@tool(
    "apps.deploy",
    description="Deploy an image tag of an app. The health check rolls a failed deploy back.",
    scope="apps:deploy",
    confirm=True,
    preview=_deploy_preview,
    input_schema={
        "type": "object",
        "properties": {
            "name": NAME,
            "tag": {"type": "string", "minLength": 1, "maxLength": 128},
            "ref": {"type": "string", "maxLength": 200},
        },
        "required": ["name", "tag"],
        "additionalProperties": False,
    },
)
def apps_deploy(db, org, caller, name: str, tag: str, ref: str | None = None):
    return service.deploy(db, int(org.id), str(org.prefix), name, tag, caller.actor, ref=ref)


@tool(
    "apps.rollback",
    description="Deploy the newest healthy tag other than the current one.",
    scope="apps:manage",
    confirm=True,
    preview=_rollback_preview,
    input_schema={"type": "object", "properties": {"name": NAME}, "required": ["name"], "additionalProperties": False},
)
def apps_rollback(db, org, caller, name: str):
    return service.rollback(db, int(org.id), str(org.prefix), name, caller.actor)
