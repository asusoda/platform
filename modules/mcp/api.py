"""HTTP mirror of the MCP tools: GET /api/tools lists them, POST /api/tools/<name> calls one.

Both take a machine token (Bearer plat_...). The body of a call is the tool's arguments as JSON.
"""

from flask import Blueprint, jsonify, request

from core.db import db_connect
from core.http.request_log import bearer_token
from core.tools import ToolError
from modules.auth import machine_tokens
from modules.mcp import runtime

tools_blueprint = Blueprint("tools", __name__)


def _caller(db):
    return machine_tokens.verify(db, bearer_token())


@tools_blueprint.route("", methods=["GET"])
def list_tools():
    db = db_connect.SessionLocal()
    try:
        caller = _caller(db)
        if caller is None:
            return jsonify({"error": "A valid machine token is required"}), 401
        try:
            return jsonify({"tools": [runtime.describe(spec) for spec in runtime.available(db, caller)]})
        except ToolError as e:
            return jsonify({"error": e.message}), e.status
    finally:
        db.close()


@tools_blueprint.route("/<string:name>", methods=["POST"])
def call_tool(name):
    db = db_connect.SessionLocal()
    try:
        caller = _caller(db)
        if caller is None:
            return jsonify({"error": "A valid machine token is required"}), 401
        arguments = request.get_json(silent=True)
        if arguments is not None and not isinstance(arguments, dict):
            return jsonify({"error": "Body must be a JSON object of arguments"}), 400
        try:
            return jsonify({"result": runtime.call(db, caller, name, arguments, source="api")})
        except ToolError as e:
            return jsonify({"error": e.message}), e.status
    finally:
        db.close()
