"""HTTP routes for pods. Officers manage an org's pods; members list and connect to the ones shared with them."""

import io
from typing import cast

from flask import Blueprint, jsonify, request, send_file

from modules.auth import access
from modules.auth.decoraters import auth_required, member_required
from modules.organizations.models import Organization
from shared import db_connect

from . import files, schedule, service

compute_blueprint = Blueprint("compute", __name__)


def _body():
    return request.get_json(silent=True)


def _officer_route(rule: str, methods: list[str]):
    """An officer route under /<org_prefix>. The view gets (db, org, **path args)."""

    def decorator(view):
        def wrapper(org_prefix, **kwargs):
            db = db_connect.SessionLocal()
            try:
                org = db.query(Organization).filter_by(prefix=org_prefix, is_active=True).first()
                if org is None:
                    return jsonify({"error": "Organization not found"}), 404
                result = view(db, org, **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except (service.ComputeError, files.FilesError) as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        compute_blueprint.route(f"/<string:org_prefix>{rule}", methods=methods)(auth_required(wrapper))
        return view

    return decorator


def _member_route(rule: str, methods: list[str]):
    """A member route under /<org_prefix>/me. The view gets (db, org, discord_id, **path args)."""

    def decorator(view):
        def wrapper(org_prefix, user_discord_id=None, organization=None, **kwargs):
            db = db_connect.SessionLocal()
            try:
                result = view(db, organization, str(user_discord_id), **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except service.ComputeError as e:
                db.rollback()
                return jsonify({"error": e.message}), e.status
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        compute_blueprint.route(f"/<string:org_prefix>/me{rule}", methods=methods)(member_required(wrapper))
        return view

    return decorator


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
    return {"pod": service.create_pod(db, _org_id(org), _body(), _caller())}, 201


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
