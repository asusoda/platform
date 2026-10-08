"""HTTP routes for pods. Officers manage an org's pods; members list and connect to the ones shared with them."""

import functools
import html
import io
import secrets
from typing import cast

from flask import Blueprint, jsonify, redirect, request, send_file, session

from core import audit
from core.config import config
from core.db import db_connect
from modules.accounts import providers
from modules.auth import access
from modules.auth.routes import member_view, officer_route, respond
from modules.organizations import service as organizations
from modules.organizations.models import Organization

from . import cli_login, files, schedule, service

compute_blueprint = Blueprint("compute", __name__)


def _body():
    return request.get_json(silent=True)


_officer_route = functools.partial(officer_route, compute_blueprint)


def _member_route(rule: str, methods: list[str]):
    """A member route under /<org_prefix>/me. The view gets (db, org, discord_id, **path args).

    Members come with a Discord login session or with a compute CLI token (Bearer plat_...).
    """

    def decorator(view):
        session_route = member_view(view)

        def wrapper(org_prefix, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer plat_"):
                return session_route(org_prefix=org_prefix, **kwargs)
            db = db_connect.SessionLocal()
            try:
                org = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()
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
        compute_blueprint.route(f"/<string:org_prefix>/me{rule}", methods=methods)(wrapper)
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


@_officer_route("/pods", ["GET"])
def list_pods(db, org):
    return {"pods": service.list_pods(db, _org_id(org))}


@_officer_route("/pods", ["POST"])
def create_pod(db, org):
    return {"pod": service.create_pod(db, _org_id(org), _body(), _caller(), config.COMPUTE_POD_IMAGE)}, 201


@_officer_route("/pods/<string:pod_id>", ["GET"])
def get_pod(db, org, pod_id):
    return {"pod": service.get_pod(db, _org_id(org), pod_id)}


@_officer_route("/pods/<string:pod_id>", ["PUT"])
def update_pod(db, org, pod_id):
    return {"pod": service.update_pod(db, _org_id(org), pod_id, _body())}


@_officer_route("/pods/<string:pod_id>/action", ["POST"])
def pod_action(db, org, pod_id):
    data = _body()
    return service.act(db, _org_id(org), pod_id, data.get("action") if isinstance(data, dict) else None)


@_member_route("/pods", ["GET"])
def my_pods(db, org, discord_id):
    return {"pods": service.accessible_pods(db, _org_id(org), discord_id)}


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
    public_key = data.get("public_key") if isinstance(data, dict) else None
    return {
        "ssh_info": service.connect(
            db, _org_id(org), pod_id, discord_id, _username(org, discord_id), _is_officer(org, discord_id), public_key
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


# Sessions: windows when a pod runs, started and stopped by the compute.schedule job.


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


# Compute CLI sign-in: Discord login in the browser, then a page with a token to paste.


def _sign_in_again() -> str:
    return f"Run {config.COMPUTE_CLI_NAME} auth again."


def _page(message: str, token: str | None = None, status: int = 200):
    block = (
        f"<p>Copy this token, run {html.escape(config.COMPUTE_CLI_NAME)} auth and paste it when asked. "
        f"It is shown once and works for {cli_login.EXPIRES_DAYS} days.</p>"
        '<pre style="padding: 1rem; background: #eee; white-space: pre-wrap; word-break: break-all">'
        f"{html.escape(token)}</pre>"
        if token
        else ""
    )
    body = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Compute CLI sign-in</title></head>'
        '<body style="font-family: system-ui, sans-serif; max-width: 36rem; margin: 4rem auto; padding: 0 1rem; '
        f'line-height: 1.5"><p>{html.escape(message)}</p>{block}</body></html>'
    )
    return body, status, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


def _callback_url() -> str:
    return f"{providers.base_url()}/api/compute/cli/callback"


@compute_blueprint.route("/<string:org_prefix>/cli/login", methods=["GET"])
def cli_sign_in(org_prefix):
    if not providers.base_url():
        return _page("This server has no ACCOUNTS_BASE_URL, so Discord sign-in is not set up.", status=503)
    state = secrets.token_urlsafe(24)
    session["compute_cli_login"] = {"state": state, "org_prefix": org_prefix}
    return redirect(providers.discord_consent_url(config.CLIENT_ID, state, _callback_url()))


@compute_blueprint.route("/cli/callback", methods=["GET"])
def cli_callback():
    started = session.pop("compute_cli_login", None) or {}
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
        org = db.query(Organization).filter_by(prefix=started.get("org_prefix"), is_active=True).first()
        if org is None:
            return _page("Organization not found.", status=404)
        if not organizations.module_enabled(org, "compute"):
            return _page("Compute is turned off for this organization.", status=404)
        membership = _is_member(org, discord_id)
        if membership is None:
            return _page("Discord is not available right now. Try again shortly.", status=503)
        org_name = str(org.name)
        if not membership:
            return _page(f"You need to be in the {org_name} Discord server to use its pods.", status=403)
        token = cli_login.issue(db, _org_id(org), discord_id)
    finally:
        db.close()
    audit.record(
        "compute cli token issued",
        source="http",
        org=str(started.get("org_prefix")),
        actor_kind="member",
        actor_id=discord_id,
    )
    return _page(f"Signed in to {org_name}.", token)
