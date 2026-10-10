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
