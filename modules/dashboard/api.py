"""HTTP routes for the officer dashboard: one overview of the organization, its branding and its CI runs."""

from functools import partial

from flask import Blueprint

from core.http.responses import json_body
from modules.auth.routes import officer_route
from modules.organizations import service as organizations

from . import ci, service

dashboard_blueprint = Blueprint("dashboard", __name__)
_route = partial(officer_route, dashboard_blueprint)


@_route("/overview", ["GET"])
def overview(db, org):
    return service.overview(db, org)


@_route("/branding", ["GET"])
def get_branding(db, org):
    return organizations.branding(org)


@_route("/branding", ["PUT"])
def set_branding(db, org):
    return organizations.set_branding(db, org, json_body())


@_route("/ci", ["GET"])
def ci_runs(db, org):
    return ci.runs(db, org)


@_route("/ci/repos", ["PUT"])
def set_ci_repos(db, org):
    return {"repos": ci.set_repos(db, org, json_body().get("repos"))}
