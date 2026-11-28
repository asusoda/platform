"""App manifests: the schema every provider shares, the provider checks, and manifest files in GitHub repos.

No Flask here. A manifest names the image, the health check and the hardware. memory and cpus apply to every
provider: This server caps the container with them, and RunPod picks the smallest CPU flavor for them when the
manifest has no gpu and no cpu. A field that only one provider reads says so in its description.
"""

import re
from typing import Any
from urllib.parse import quote

import jsonschema
import requests
import yaml

from core import hosting, secrets
from core.integrations import github
from hosting import base
from hosting.base import AppError

GITHUB_SECRET = github.SECRET_NAME

# Two dashes in a row separate the org and the app in a container name on This server
NAME_PATTERN = re.compile(r"^(?!.*--)[a-z0-9][a-z0-9-]{0,62}$")
TAG_PATTERN = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|sha256:[a-f0-9]{64})$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
PATH_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}$")
REF_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,99}$")
DEFAULT_MANIFEST_PATH = "platform.app.yaml"
# The app template routes use this path segment, so no app has this name
RESERVED_NAME = "templates"
MAX_MANIFEST_BYTES = 100_000

_PORT = {"type": "string", "pattern": r"^[0-9]{1,5}/(http|tcp)$"}
# What an app is for. The dashboard groups apps by kind; deploys ignore it.
APP_KINDS = ("bot", "agent", "site", "service")

MANIFEST_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "kind": {"enum": list(APP_KINDS)},
        "description": {"type": "string", "maxLength": 200},
        "url": {"type": "string", "maxLength": 500, "pattern": r"^https://[^\s]+$"},
        "image": {"type": "string", "pattern": r"^[a-z0-9][a-z0-9._/-]{0,250}$"},
        "gpu": {
            "description": "RunPod: the GPU type and count",
            "type": "object",
            "properties": {"id": {"type": "string", "minLength": 1}, "count": {"type": "integer", "minimum": 1}},
            "required": ["id"],
            "additionalProperties": False,
        },
        "cpu": {
            "description": "RunPod: the CPU flavor and vCPU count. Without gpu and cpu, memory and cpus pick one",
            "type": "object",
            "properties": {"id": {"type": "string", "minLength": 1}, "vcpuCount": {"type": "integer", "minimum": 2}},
            "required": ["id", "vcpuCount"],
            "additionalProperties": False,
        },
        "cloud": {"description": "RunPod: the cloud tier", "enum": ["SECURE", "COMMUNITY"]},
        "dataCenterIds": {
            "description": "RunPod: data centers to place the pod in",
            "type": "array",
            "items": {"type": "string"},
        },
        "disk": {"description": "RunPod: the container disk in GB", "type": "integer", "minimum": 1, "maximum": 2000},
        "ports": {"type": "array", "items": _PORT},
        "args": {"description": "RunPod: the arguments of the image's command", "type": "string"},
        "registry": {"description": "RunPod: the id of the registry login for a private image", "type": "string"},
        "env": {"type": "object", "additionalProperties": {"type": "string"}},
        "secret_env": {
            "description": "Env var name to org secret name",
            "type": "object",
            "additionalProperties": {"type": "string", "pattern": r"^(app|shared)_[a-z0-9_]{1,96}$"},
        },
        "mounts": {
            "description": "RunPod: persistent (GPU pods only, 10 GB or more) and network volumes",
            "type": "object",
        },
        "memory": {
            "description": "The memory in MB. This server: the cap. RunPod: the least memory of the CPU flavor it picks",
            "type": "integer",
            "minimum": 16,
        },
        "cpus": {
            "description": "The CPUs. This server: the cap. RunPod: the least vCPUs of the CPU flavor it picks",
            "type": "number",
            "minimum": 0.05,
            "maximum": 16,
        },
        "publish": {
            "description": "This server: container port to host port, for Nginx Proxy Manager",
            "type": "object",
            "propertyNames": {"pattern": r"^[0-9]{1,5}$"},
            "additionalProperties": {"type": "integer", "minimum": 1, "maximum": 65535},
        },
        "command": {
            "description": "This server: the command and arguments in place of the image's own",
            "type": "array",
            "items": {"type": "string", "maxLength": 500},
            "maxItems": 32,
        },
        "workdir": {
            "description": "This server: the working folder in the container",
            "type": "string",
            "pattern": r"^/[^\s]{0,250}$",
        },
        "group": {
            "description": "This server: the apps of one group, the parts of one app, share a network",
            "type": "string",
            "pattern": r"^(?!.*--)[a-z0-9][a-z0-9-]{0,62}$",
        },
        "alias": {
            "description": "This server: the name the other parts of the group reach this app by, such as db",
            "type": "string",
            "pattern": r"^[a-z0-9][a-z0-9-]{0,62}$",
        },
        "volumes": {
            "description": "This server: a named folder of the app, or a host path the server allows for the org",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "pattern": r"^[a-z0-9][a-z0-9-]{0,62}$"},
                    "host": {"type": "string", "pattern": r"^/[^\s]{1,250}$"},
                    "path": {"type": "string", "pattern": r"^/[^\s]{0,250}$"},
                    "read_only": {"type": "boolean"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        "mcp": {
            "description": "The MCP server of the app, which hosting.mcp_tools and hosting.mcp_call reach (app_mcp.py)",
            "type": "object",
            "properties": {
                "url": {"type": "string", "maxLength": 500, "pattern": r"^https://[^\s]+$"},
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "path": {"type": "string", "maxLength": 200, "pattern": r"^/[^\s]*$"},
                "token_secret": {"type": "string", "pattern": r"^(app|shared)_[a-z0-9_]{1,96}$"},
            },
            "anyOf": [{"required": ["url"]}, {"required": ["port"]}],
            "additionalProperties": False,
        },
        "access": {
            "description": "Shared apps: what an org's subscription does in the app (hosting/shared.py)",
            "type": "object",
            "properties": {"kind": {"enum": ["vaultwarden"]}},
            "required": ["kind"],
            "additionalProperties": False,
        },
        "health": {
            "type": "object",
            "properties": {
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "path": {"type": "string", "pattern": r"^/[^\s]*$"},
                "tcp": {
                    "description": "This server: check that the port accepts a connection, for a database",
                    "const": True,
                },
                "running": {
                    "description": "This server: healthy while the container runs, for a part with no port",
                    "const": True,
                },
            },
            "oneOf": [{"required": ["port", "path"]}, {"required": ["port", "tcp"]}, {"required": ["running"]}],
            "additionalProperties": False,
        },
    },
    "required": ["image", "health"],
    "additionalProperties": False,
}


def validated(manifest: Any, provider: str | None = None) -> dict:
    """The manifest after the schema check and, with provider, that provider's own check."""
    try:
        jsonschema.validate(manifest, MANIFEST_SCHEMA)
    except jsonschema.ValidationError as e:
        raise AppError(f"Invalid manifest: {e.message}") from e
    if provider is not None:
        try:
            base.provider(provider).validate(manifest)
        except hosting.HostingError as e:
            raise AppError(f"Invalid manifest: {e.message}") from e
    return manifest


def safe_path(value: str, pattern: re.Pattern, name: str) -> str:
    if not isinstance(value, str) or not pattern.match(value) or ".." in value:
        raise AppError(f"{name} is not valid")
    return value


def fetch_manifest(db, org_id: int | None, repo: str, path: str, ref: str | None) -> dict:
    """The manifest file in a GitHub repo at ref (the default branch when None), validated."""
    url = f"https://api.github.com/repos/{repo}/contents/{quote(path)}"
    headers = {"Accept": "application/vnd.github.raw+json", "User-Agent": "platform-hosting"}
    token = secrets.get_secret(db, org_id, GITHUB_SECRET) if org_id is not None else None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(url, params={"ref": ref} if ref else {}, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise AppError("GitHub could not be reached", 502) from e
    where = f"{repo} at {ref or 'its default branch'}"
    if response.status_code == 404:
        raise AppError(f"{path} was not found in {where}; private repos need the org secret {GITHUB_SECRET}", 422)
    if response.status_code != 200:
        raise AppError(f"GitHub answered {response.status_code} for {path} in {where}", 502)
    if len(response.content) > MAX_MANIFEST_BYTES:
        raise AppError(f"{path} is larger than {MAX_MANIFEST_BYTES} bytes", 422)
    try:
        manifest = yaml.safe_load(response.text)
    except yaml.YAMLError as e:
        raise AppError(f"{path} in {where} is not valid YAML", 422) from e
    try:
        return validated(manifest)
    except AppError as e:
        raise AppError(f"{path} in {where}: {e.message}", 422) from e
