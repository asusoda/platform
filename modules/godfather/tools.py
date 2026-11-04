"""Godfather pod tools."""

from core.config import config
from core.tools import tool

from . import files, schedule, service


@tool(
    "godfather.pods",
    description=(
        "The org's Godfather pods with their live status, hardware, who may connect, the image version, "
        "image_current (false: members cannot connect until the pod is recreated) and pod admin."
    ),
    scope="godfather:manage",
    module="godfather",
)
def godfather_pods(db, org, caller):
    return {"pods": service.list_pods(db, int(org.id))}


@tool(
    "godfather.pod_action",
    description=(
        "Start, stop, restart, terminate or recreate a pod. Terminate deletes the pod and its volume. Recreate "
        "replaces the pod with a new one from the default image and deletes the old pod and its disk."
    ),
    scope="godfather:manage",
    module="godfather",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {
            "pod_id": {"type": "string", "minLength": 1, "maxLength": 64},
            "action": {"type": "string", "enum": list(service.ACTIONS)},
        },
        "required": ["pod_id", "action"],
        "additionalProperties": False,
    },
)
def godfather_pod_action(db, org, caller, pod_id: str, action: str):
    image = service.pod_image(db, int(org.id), config.GODFATHER_POD_IMAGE)
    return service.act(db, int(org.id), pod_id, action, default_image=image)


@tool(
    "godfather.pod_members",
    description="Who may connect to a pod, and who got a certificate for it in the last 90 days, newest first.",
    scope="godfather:manage",
    module="godfather",
    input_schema={
        "type": "object",
        "properties": {"pod_id": {"type": "string", "minLength": 1, "maxLength": 64}},
        "required": ["pod_id"],
        "additionalProperties": False,
    },
)
def godfather_pod_members(db, org, caller, pod_id: str):
    return service.pod_members(db, int(org.id), pod_id)


POD_ID = {"type": "string", "minLength": 1, "maxLength": 64}
PATH = {"type": "string", "minLength": 1, "maxLength": 1000}
DISCORD_IDS = {
    "type": "array",
    "items": {"type": "string", "pattern": "^[0-9]{5,25}$"},
    "maxItems": service.MAX_ALLOWED_USERS,
}


def _object(properties: dict, required: tuple[str, ...] = (), **extra) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
        **extra,
    }


@tool(
    "godfather.create_pod",
    description=(
        "Create a pod on the org's RunPod account. It costs money while it runs. Without image_name it uses the "
        "org's pod image. allowed_users are Discord ids of members who may connect; is_public lets every member."
    ),
    scope="godfather:manage",
    module="godfather",
    confirm=True,
    input_schema=_object(
        {
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "image_name": {"type": "string", "minLength": 1, "maxLength": 200},
            "provider": {"type": "string", "maxLength": 32},
            "cloud_type": {"type": "string", "enum": list(service.CLOUD_TYPES)},
            "use_cpu_only": {"type": "boolean"},
            "gpu_type_id": {"type": "string", "maxLength": 100},
            "cpu_flavor": {"type": "string", "maxLength": 50},
            "vcpu_count": {"type": "integer", "minimum": 2, "maximum": 64},
            "volume_in_gb": {"type": "integer", "minimum": 0, "maximum": 2000},
            "container_disk_in_gb": {"type": "integer", "minimum": 1, "maximum": 500},
            "volume_mount_path": {"type": "string", "maxLength": 200},
            "env": {"type": "object", "additionalProperties": {"type": "string"}},
            "is_public": {"type": "boolean"},
            "allowed_users": DISCORD_IDS,
        }
    ),
)
def godfather_create_pod(db, org, caller, **data):
    image = service.pod_image(db, int(org.id), config.GODFATHER_POD_IMAGE)
    return {"pod": service.create_pod(db, int(org.id), data, caller.actor, image)}


@tool(
    "godfather.update_pod",
    description="Change who may connect to a pod: is_public, allowed_users (Discord ids), or both.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object(
        {"pod_id": POD_ID, "is_public": {"type": "boolean"}, "allowed_users": DISCORD_IDS},
        ("pod_id",),
        minProperties=2,
    ),
)
def godfather_update_pod(db, org, caller, pod_id: str, **data):
    return {"pod": service.update_pod(db, int(org.id), pod_id, data)}


@tool(
    "godfather.connected",
    description="The SSH sessions open on a pod now, with the member of each.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_id": POD_ID}, ("pod_id",)),
)
def godfather_connected(db, org, caller, pod_id: str):
    return service.connected_now(db, int(org.id), pod_id)


@tool(
    "godfather.settings",
    description="The org's default pod image, or null, and the deployment's image that it falls back to.",
    scope="godfather:manage",
    module="godfather",
)
def godfather_settings(db, org, caller):
    return {"settings": service.godfather_settings(db, int(org.id), config.GODFATHER_POD_IMAGE)}


@tool(
    "godfather.update_settings",
    description="Set the org's default pod image. null or an empty string goes back to the deployment's image.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_image": {"type": ["string", "null"], "maxLength": 200}}, ("pod_image",)),
)
def godfather_update_settings(db, org, caller, pod_image: str | None):
    data = {"pod_image": pod_image}
    return {"settings": service.update_godfather_settings(db, int(org.id), data, config.GODFATHER_POD_IMAGE)}


@tool(
    "godfather.sessions",
    description="A pod's sessions: the times the schedule job starts and stops it.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_id": POD_ID}, ("pod_id",)),
)
def godfather_sessions(db, org, caller, pod_id: str):
    return {"sessions": schedule.list_sessions(db, int(org.id), pod_id)}


@tool(
    "godfather.add_session",
    description=(
        "Schedule a session: the schedule job starts the pod at start_at and stops it at stop_at (ISO 8601, at "
        "most 24 hours). The pod costs money while it runs."
    ),
    scope="godfather:manage",
    module="godfather",
    confirm=True,
    input_schema=_object(
        {
            "pod_id": POD_ID,
            "start_at": {"type": "string", "maxLength": 40},
            "stop_at": {"type": "string", "maxLength": 40},
            "title": {"type": "string", "maxLength": 200},
        },
        ("pod_id", "start_at", "stop_at"),
    ),
)
def godfather_add_session(db, org, caller, pod_id: str, **data):
    return {"session": schedule.add_session(db, int(org.id), pod_id, data, caller.actor)}


@tool(
    "godfather.delete_session",
    description="Remove a session. If the session has started, the next schedule run stops the pod.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_id": POD_ID, "session_id": {"type": "integer"}}, ("pod_id", "session_id")),
)
def godfather_delete_session(db, org, caller, pod_id: str, session_id: int):
    schedule.delete_session(db, int(org.id), pod_id, session_id)
    return {"deleted": session_id}


@tool(
    "godfather.list_files",
    description="The files in a folder of a running pod, as root. path defaults to /workspace.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_id": POD_ID, "path": PATH}, ("pod_id",)),
)
def godfather_list_files(db, org, caller, pod_id: str, path: str = "/workspace"):
    with service.pod_files(db, int(org.id), pod_id) as pod:
        return {"path": files.clean_path(path), "files": pod.list(path)}


@tool(
    "godfather.read_file",
    description=f"The text of a file on a running pod, up to {files.MAX_READ_BYTES} bytes.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_id": POD_ID, "path": PATH}, ("pod_id", "path")),
)
def godfather_read_file(db, org, caller, pod_id: str, path: str):
    with service.pod_files(db, int(org.id), pod_id) as pod:
        return {"path": files.clean_path(path), "content": pod.read_text(path)}


@tool(
    "godfather.write_file",
    description="Write a text file on a running pod. It replaces a file with that path.",
    scope="godfather:manage",
    module="godfather",
    confirm=True,
    input_schema=_object(
        {"pod_id": POD_ID, "path": PATH, "content": {"type": "string", "maxLength": files.MAX_READ_BYTES}},
        ("pod_id", "path", "content"),
    ),
)
def godfather_write_file(db, org, caller, pod_id: str, path: str, content: str):
    with service.pod_files(db, int(org.id), pod_id) as pod:
        pod.write_text(path, content)
    return {"path": files.clean_path(path)}


@tool(
    "godfather.make_folder",
    description="Make a folder on a running pod.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_id": POD_ID, "path": PATH}, ("pod_id", "path")),
)
def godfather_make_folder(db, org, caller, pod_id: str, path: str):
    with service.pod_files(db, int(org.id), pod_id) as pod:
        pod.mkdir(path)
    return {"path": files.clean_path(path)}


@tool(
    "godfather.move_file",
    description="Rename or move a file or folder on a running pod.",
    scope="godfather:manage",
    module="godfather",
    input_schema=_object({"pod_id": POD_ID, "old_path": PATH, "new_path": PATH}, ("pod_id", "old_path", "new_path")),
)
def godfather_move_file(db, org, caller, pod_id: str, old_path: str, new_path: str):
    with service.pod_files(db, int(org.id), pod_id) as pod:
        pod.rename(old_path, new_path)
    return {"path": files.clean_path(new_path)}


@tool(
    "godfather.delete_file",
    description="Delete a file, or a folder and all it holds, on a running pod.",
    scope="godfather:manage",
    module="godfather",
    confirm=True,
    input_schema=_object({"pod_id": POD_ID, "path": PATH}, ("pod_id", "path")),
)
def godfather_delete_file(db, org, caller, pod_id: str, path: str):
    with service.pod_files(db, int(org.id), pod_id) as pod:
        pod.delete(path)
    return {"deleted": files.clean_path(path)}
