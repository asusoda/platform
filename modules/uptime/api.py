"""HTTP routes for officers to manage the uptime monitors of their org."""

from functools import partial

from flask import Blueprint

from core.http.responses import json_body
from modules.auth.routes import officer_route

from . import service

uptime_blueprint = Blueprint("uptime", __name__)
_route = partial(officer_route, uptime_blueprint)


@_route("/monitors", ["GET"])
def list_monitors(db, org):
    return {"monitors": service.list_monitors(db, int(org.id))}


@_route("/monitors", ["POST"])
def create_monitor(db, org):
    return {"monitor": service.create_monitor(db, int(org.id), json_body())}, 201


@_route("/monitors/<int:monitor_id>", ["GET"])
def get_monitor(db, org, monitor_id):
    return {"monitor": service.get_monitor(db, int(org.id), monitor_id)}


@_route("/monitors/<int:monitor_id>", ["PUT"])
def update_monitor(db, org, monitor_id):
    return {"monitor": service.update_monitor(db, int(org.id), monitor_id, json_body())}


@_route("/monitors/<int:monitor_id>", ["DELETE"])
def delete_monitor(db, org, monitor_id):
    service.delete_monitor(db, int(org.id), monitor_id)
    return {"deleted": True}


@_route("/monitors/<int:monitor_id>/check", ["POST"])
def check_monitor(db, org, monitor_id):
    """Check the monitor now and wait for the result, at most its timeout."""
    return service.check_now(db, int(org.id), monitor_id)


@_route("/targets", ["GET"])
def list_targets(db, org):
    """The Hosting apps that a monitor can check."""
    return {"apps": service.targets(db, int(org.id))}
