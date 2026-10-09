"""Compute pod tools."""

from core.tools import tool

from . import service


@tool(
    "compute.pods",
    description="The org's compute pods with their live status, hardware and who may connect.",
    scope="compute:manage",
    module="compute",
)
def compute_pods(db, org, caller):
    return {"pods": service.list_pods(db, int(org.id))}


@tool(
    "compute.pod_action",
    description="Start, stop, restart or terminate a pod. Terminate deletes the pod and its volume.",
    scope="compute:manage",
    module="compute",
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
def compute_pod_action(db, org, caller, pod_id: str, action: str):
    return service.act(db, int(org.id), pod_id, action)


@tool(
    "compute.pod_members",
    description="Who may connect to a pod, and who got a certificate for it in the last 90 days, newest first.",
    scope="compute:manage",
    module="compute",
    input_schema={
        "type": "object",
        "properties": {"pod_id": {"type": "string", "minLength": 1, "maxLength": 64}},
        "required": ["pod_id"],
        "additionalProperties": False,
    },
)
def compute_pod_members(db, org, caller, pod_id: str):
    return service.pod_members(db, int(org.id), pod_id)
