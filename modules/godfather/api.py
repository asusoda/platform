"""HTTP routes for pods. Officers manage an org's pods; members list and connect to the ones shared with them."""

import functools
import html
import io
import secrets
from typing import cast
from urllib.parse import urlencode

from flask import Blueprint, jsonify, redirect, request, send_file, session

from core import audit
from core.config import config
from core.db import db_connect
from core.errors import ServiceError
from core.integrations.discord import DiscordUnavailable
from core.log import get_logger
from modules.accounts import providers
from modules.auth import access
from modules.auth.routes import member_view, officer_route, respond
from modules.organizations import service as organizations

from . import cli_login, files, schedule, service

godfather_blueprint = Blueprint("godfather", __name__)
logger = get_logger(__name__)


def _body():
    return request.get_json(silent=True)


_officer_route = functools.partial(officer_route, godfather_blueprint)


def _member_route(rule: str, methods: list[str]):
    """A member route under /<org_prefix>/me. The view gets (db, org, discord_id, **path args).

    Members come with a Discord login session or with a Godfather CLI token (Bearer plat_...).
    """

    def decorator(view):
        session_route = member_view(view)

        def wrapper(org_prefix, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer plat_"):
                return session_route(org_prefix=org_prefix, **kwargs)
            db = db_connect.SessionLocal()
            try:
                org = organizations.find_by_prefix(db, org_prefix, active_only=True)
                if org is None:
                    return jsonify({"error": "Organization not found"}), 404
                discord_id = cli_login.member_for(db, _org_id(org), header[7:].strip())
                if discord_id is None:
                    return jsonify({"error": f"The CLI token is invalid or expired. {_sign_in_again()}"}), 401
                membership = _is_member(org, discord_id)
                if membership is None:
                    return jsonify({"error": "Discord is not available; try again shortly"}), 503
                if not membership:
                    return jsonify({"error": "You are no longer a member of this organization"}), 403
                return respond(db, view, org, str(discord_id), **kwargs)
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        godfather_blueprint.route(f"/<string:org_prefix>/me{rule}", methods=methods)(wrapper)
        return view

    return decorator


def _is_member(org, discord_id: str) -> bool | None:
    directory = access.discord_directory()
    if directory is None or not directory.is_ready():
        return None
    return bool(directory.check_user_membership(int(discord_id), int(org.guild_id)))


def _org_id(org) -> int:
    return cast(int, org.id)


def _caller() -> str | None:
    principal = access.current_principal()
    return principal.discord_id if principal else None


def _with_owner(pod: dict) -> dict:
    """The pod with can_change_admin: the caller is its owner or the superadmin."""
    caller = _caller()
    allowed = bool(caller) and (pod.get("owner") == caller or access.is_superadmin(str(caller)))
    return pod | {"can_change_admin": allowed}


@_officer_route("/pods", ["GET"])
def list_pods(db, org):
    return {"pods": [_with_owner(p) for p in service.list_pods(db, _org_id(org))]}


@_officer_route("/pods", ["POST"])
def create_pod(db, org):
    image = service.pod_image(db, _org_id(org), config.GODFATHER_POD_IMAGE)
    return {"pod": service.create_pod(db, _org_id(org), _body(), _caller(), image)}, 201


@_officer_route("/settings", ["GET"])
def get_settings(db, org):
    return {"settings": service.godfather_settings(db, _org_id(org), config.GODFATHER_POD_IMAGE)}


@_officer_route("/settings", ["PUT"])
def put_settings(db, org):
    return {"settings": service.update_godfather_settings(db, _org_id(org), _body(), config.GODFATHER_POD_IMAGE)}


@_officer_route("/pods/<string:pod_id>", ["GET"])
def get_pod(db, org, pod_id):
    return {"pod": _with_owner(service.get_pod(db, _org_id(org), pod_id))}


@_officer_route("/pods/<string:pod_id>", ["PUT"])
def update_pod(db, org, pod_id):
    return {"pod": service.update_pod(db, _org_id(org), pod_id, _body())}


@_officer_route("/pods/<string:pod_id>/action", ["POST"])
def pod_action(db, org, pod_id):
    data = _body()
    image = service.pod_image(db, _org_id(org), config.GODFATHER_POD_IMAGE)
    action = data.get("action") if isinstance(data, dict) else None
    return service.act(db, _org_id(org), pod_id, action, default_image=image)


@_officer_route("/pods/<string:pod_id>/admin", ["PUT"])
def pod_admin(db, org, pod_id):
    data = _body()
    enabled = data.get("enabled") if isinstance(data, dict) else None
    caller = _caller()
    pod = service.set_pod_admin(
        db, _org_id(org), pod_id, enabled, caller, bool(caller) and access.is_superadmin(str(caller))
    )
    return {"pod": _with_owner(pod)}


def _name_lookup(org):
    """A function from a Discord id to the member's display name in the org's server, or None."""
    directory = access.discord_directory()
    if directory is None or not directory.is_ready():
        return None

    failed: list[bool] = []

    def name_of(discord_id: str) -> str | None:
        if failed:
            return None
        try:
            return directory.get_display_name(org.guild_id, discord_id)
        except DiscordUnavailable:
            # Stop after the first failure so one request does not wait on Discord many times
            failed.append(True)
            return None

    return name_of


@_officer_route("/pods/<string:pod_id>/members", ["GET"])
def pod_members(db, org, pod_id):
    return service.pod_members(db, _org_id(org), pod_id, _name_lookup(org))


@_officer_route("/pods/<string:pod_id>/members/connected", ["GET"])
def pod_connected(db, org, pod_id):
    return service.connected_now(db, _org_id(org), pod_id, _name_lookup(org))


@_officer_route("/members", ["GET"])
def find_members(db, org):
    """Server members for the allowed members field.

    ?ids= names the given ids. Otherwise ?q= searches names, ?role= keeps the holders of one role, and
    ?limit= (1 to 500, default 50) caps the list. Without q the whole member list is read.
    """
    directory = access.discord_directory()
    if directory is None or not directory.is_ready():
        return {"error": "Discord is not set up, so members cannot be looked up. Enter Discord ids."}, 503
    query = (request.args.get("q") or "").strip()[:100]
    role = (request.args.get("role") or "").strip()
    ids = [i for i in (request.args.get("ids") or "").split(",") if i.isdigit()][:50]
    limit = max(1, min(request.args.get("limit", type=int) or 50, service.MAX_ALLOWED_USERS))
    try:
        if ids:
            names = {i: directory.get_display_name(org.guild_id, i) for i in ids}
            return {"members": [{"id": i, "name": name} for i, name in names.items() if name]}
        return service.member_page(directory, org.guild_id, query, role if role.isdigit() else "", limit)
    except DiscordUnavailable as e:
        logger.warning("member lookup failed for org %s: %s", org.id, e)
        if "403" in str(e) and not query:
            return {"error": _NO_MEMBERS_INTENT}, 503
        return {"error": "Discord did not answer the member search. Enter Discord ids."}, 503


_NO_MEMBERS_INTENT = (
    "Discord refused the member list. Turn on Server Members Intent for the bot in the Discord Developer Portal "
    "(Bot > Privileged Gateway Intents), or search by name."
)


@_member_route("/pods", ["GET"])
def my_pods(db, org, discord_id):
    return {"pods": service.accessible_pods(db, _org_id(org), discord_id)}


@_member_route("/sessions", ["GET"])
def my_sessions(db, org, discord_id):
    return {"sessions": schedule.member_sessions(db, _org_id(org), discord_id)}


def _is_officer(org, discord_id: str) -> bool:
    if access.is_superadmin(discord_id):
        return True
    guilds = access.officer_guild_ids(discord_id)
    return guilds is not None and str(org.guild_id) in guilds


def _username(org, discord_id: str) -> str:
    directory = access.discord_directory()
    member = directory.get_member(org.guild_id, discord_id) if directory is not None else None
    return str(((member or {}).get("user") or {}).get("username") or discord_id)


@_member_route("/pods/<string:pod_id>/connect", ["POST"])
def connect(db, org, discord_id, pod_id):
    data = _body()
    data = data if isinstance(data, dict) else {}
    return {
        "ssh_info": service.connect(
            db,
            _org_id(org),
            pod_id,
            discord_id,
            _username(org, discord_id),
            _is_officer(org, discord_id),
            data.get("admin") is True,
            data.get("public_key"),
        )
    }


# File manager: officers browse and edit files on a running pod as root.


def _json() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _files(db, org, pod_id):
    return service.pod_files(db, _org_id(org), pod_id)


@_officer_route("/pods/<string:pod_id>/files", ["GET"])
def list_files(db, org, pod_id):
    path = request.args.get("path", "/workspace")
    with _files(db, org, pod_id) as pod:
        return {"path": files.clean_path(path), "files": pod.list(path)}


@_officer_route("/pods/<string:pod_id>/files/read", ["POST"])
def read_file(db, org, pod_id):
    path = _json().get("path")
    with _files(db, org, pod_id) as pod:
        return {"path": files.clean_path(path), "content": pod.read_text(path)}


@_officer_route("/pods/<string:pod_id>/files/write", ["POST"])
def write_file(db, org, pod_id):
    data = _json()
    with _files(db, org, pod_id) as pod:
        pod.write_text(data.get("path"), data.get("content"))
    return {"path": files.clean_path(data.get("path"))}


@_officer_route("/pods/<string:pod_id>/files/download", ["POST"])
def download_file(db, org, pod_id):
    path = files.clean_path(_json().get("path"))
    with _files(db, org, pod_id) as pod:
        content = pod.download(path)
    return send_file(io.BytesIO(content), as_attachment=True, download_name=path.rsplit("/", 1)[-1] or "file"), 200


@_officer_route("/pods/<string:pod_id>/files/upload", ["POST"])
def upload_file(db, org, pod_id):
    if (request.content_length or 0) > files.MAX_TRANSFER_BYTES:
        raise files.FilesError(f"Uploads are limited to {files.MAX_TRANSFER_BYTES} bytes", 413)
    upload = request.files.get("file")
    if upload is None:
        raise files.FilesError("Send the file as multipart field file")
    with _files(db, org, pod_id) as pod:
        return {"path": pod.upload(request.form.get("path", "/workspace"), upload.filename, upload.stream)}


@_officer_route("/pods/<string:pod_id>/files/mkdir", ["POST"])
def make_directory(db, org, pod_id):
    path = _json().get("path")
    with _files(db, org, pod_id) as pod:
        pod.mkdir(path)
    return {"path": files.clean_path(path)}


@_officer_route("/pods/<string:pod_id>/files/rename", ["POST"])
def rename_file(db, org, pod_id):
    data = _json()
    with _files(db, org, pod_id) as pod:
        pod.rename(data.get("old_path"), data.get("new_path"))
    return {"path": files.clean_path(data.get("new_path"))}


@_officer_route("/pods/<string:pod_id>/files/delete", ["POST"])
def delete_file(db, org, pod_id):
    path = _json().get("path")
    with _files(db, org, pod_id) as pod:
        pod.delete(path)
    return {"deleted": files.clean_path(path)}


# Sessions: windows when a pod runs, started and stopped by the godfather.schedule job.


@_officer_route("/pods/<string:pod_id>/sessions", ["GET"])
def list_sessions(db, org, pod_id):
    return {"sessions": schedule.list_sessions(db, _org_id(org), pod_id)}


@_officer_route("/pods/<string:pod_id>/sessions", ["POST"])
def add_session(db, org, pod_id):
    return {"session": schedule.add_session(db, _org_id(org), pod_id, _body(), _caller())}, 201


@_officer_route("/pods/<string:pod_id>/sessions/<int:session_id>", ["DELETE"])
def delete_session(db, org, pod_id, session_id):
    schedule.delete_session(db, _org_id(org), pod_id, session_id)
    return {"deleted": session_id}


# Godfather CLI sign-in: Discord login in the browser. The token goes back to a CLI that listens on
# 127.0.0.1 as a one-time code, or shows on a page to paste.


def _sign_in_again() -> str:
    return f"Run {config.GODFATHER_CLI_NAME} auth again."


def _page(message: str, token: str | None = None, status: int = 200):
    block = (
        f"<p>Copy this token, run {html.escape(config.GODFATHER_CLI_NAME)} auth and paste it when asked. "
        f"It is shown once and works for {cli_login.EXPIRES_DAYS} days.</p>"
        '<pre style="padding: 1rem; background: #eee; white-space: pre-wrap; word-break: break-all">'
        f"{html.escape(token)}</pre>"
        if token
        else ""
    )
    body = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Godfather CLI sign-in</title></head>'
        '<body style="font-family: system-ui, sans-serif; max-width: 36rem; margin: 4rem auto; padding: 0 1rem; '
        f'line-height: 1.5"><p>{html.escape(message)}</p>{block}</body></html>'
    )
    return body, status, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


def _callback_url() -> str:
    return f"{providers.base_url()}/api/compute/cli/callback"


@godfather_blueprint.route("/<string:org_prefix>/cli/login", methods=["GET"])
def cli_sign_in(org_prefix):
    if not providers.base_url():
        return _page("This server has no ACCOUNTS_BASE_URL, so Discord sign-in is not set up.", status=503)
    try:
        cli = cli_login.loopback(
            request.args.get("port"),
            request.args.get("state"),
            request.args.get("code_challenge"),
            request.args.get("code_challenge_method"),
        )
    except ServiceError as e:
        return _page(f"{e.message}. {_sign_in_again()}", status=400)
    state = secrets.token_urlsafe(24)
    session["godfather_cli_login"] = {"state": state, "org_prefix": org_prefix, "cli": cli}
    return redirect(providers.discord_consent_url(config.CLIENT_ID, state, _callback_url()))


@godfather_blueprint.route("/cli/callback", methods=["GET"])
def cli_callback():
    started = session.pop("godfather_cli_login", None) or {}
    if not started.get("state") or started["state"] != request.args.get("state") or not request.args.get("code"):
        return _page(f"This sign-in was not started here, or was cancelled. {_sign_in_again()}", status=400)
    try:
        discord_id = providers.discord_user_id(
            config.CLIENT_ID, config.CLIENT_SECRET, request.args["code"], _callback_url()
        )
    except providers.ProviderError:
        return _page(f"Discord sign-in failed. {_sign_in_again()}", status=502)
    db = db_connect.SessionLocal()
    try:
        org = organizations.find_by_prefix(db, started.get("org_prefix"), active_only=True)
        if org is None:
            return _page("Organization not found.", status=404)
        if not organizations.module_enabled(org, "godfather"):
            return _page("Godfather is turned off for this organization.", status=404)
        membership = _is_member(org, discord_id)
        if membership is None:
            return _page("Discord is not available right now. Try again shortly.", status=503)
        org_name = str(org.name)
        if not membership:
            return _page(f"You need to be in the {org_name} Discord server to use its pods.", status=403)
        cli = started.get("cli")
        if cli:
            code = cli_login.start_code(db, _org_id(org), discord_id, cli["code_challenge"])
            # The host is fixed, so the redirect only reaches the member's own machine.
            query = urlencode({"code": code, "state": cli["state"]})
            return redirect(f"http://127.0.0.1:{int(cli['port'])}/callback?{query}")
        token = cli_login.issue(db, _org_id(org), discord_id)
    finally:
        db.close()
    audit.record(
        "godfather cli token issued",
        source="http",
        org=str(started.get("org_prefix")),
        actor_kind="member",
        actor_id=discord_id,
    )
    return _page(f"Signed in to {org_name}.", token)


_NO_STORE = {"Cache-Control": "no-store"}


@godfather_blueprint.route("/<string:org_prefix>/cli/token", methods=["POST"])
def cli_token(org_prefix):
    """Trade a code from the loopback sign-in and its PKCE verifier for a CLI token."""
    data = _body()
    data = data if isinstance(data, dict) else {}
    db = db_connect.SessionLocal()
    try:
        org = organizations.find_by_prefix(db, org_prefix, active_only=True)
        if org is None:
            return jsonify({"error": "Organization not found"}), 404, _NO_STORE
        try:
            token, discord_id = cli_login.redeem(db, _org_id(org), data.get("code"), data.get("code_verifier"))
        except ServiceError as e:
            db.rollback()
            return jsonify({"error": e.message}), e.status, _NO_STORE
    finally:
        db.close()
    audit.record("godfather cli token issued", source="http", org=org_prefix, actor_kind="member", actor_id=discord_id)
    return jsonify({"token": token, "expires_days": cli_login.EXPIRES_DAYS}), 200, _NO_STORE
