"""Records every successful API write in the audit log, after the response is sent."""

from flask import Flask, g, request
from sqlalchemy import text

from core.audit import _session, logger, record
from core.request_log import _credential, _org

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Writes that are too frequent or carry nothing worth keeping; tool calls audit themselves.
# Modules add their own per-request writes here.
SKIPPED_ROUTES = {"/api/auth/refresh", "/api/tools/<string:name>"}
# Reads that change state
AUDITED_READS = {"/api/auth/appToken"}


def _org_prefix(db) -> str | None:
    """The org the request names, as a prefix (routes use either a prefix or a numeric id)."""
    args = request.view_args or {}
    if "org_prefix" in args:
        return str(args["org_prefix"])
    if "org_id" in args:
        row = db.execute(text("SELECT prefix FROM organizations WHERE id = :id"), {"id": args["org_id"]}).first()
        return row[0] if row else str(args["org_id"])
    return _org()


def _actor(token_manager) -> tuple[str | None, str | None]:
    machine = g.get("machine_caller")
    if machine is not None:
        return "machine", f"{machine.kind}:{machine.name}#{machine.token_id}"
    kind, discord_id = _credential(token_manager)
    if discord_id:
        return kind, str(discord_id)
    email = getattr(request, "clerk_user_email", None)
    if email:
        return "clerk", email
    return kind, None


def register_audit(app: Flask, token_manager) -> None:
    """Record every successful API write."""

    @app.after_request
    def _audit_request(response):
        rule = request.url_rule.rule if request.url_rule else None
        audited = request.method in WRITE_METHODS or rule in AUDITED_READS
        if not rule or not audited or rule in SKIPPED_ROUTES or not rule.startswith("/api/"):
            return response
        if response.status_code >= 400:
            return response
        try:
            db = _session()
            try:
                org = _org_prefix(db)
            finally:
                db.close()
            kind, actor_id = _actor(token_manager)
            record(
                f"{request.method} {rule}",
                source="api",
                org=org,
                actor_kind=kind,
                actor_id=actor_id,
                status=response.status_code,
                details={"path": request.path},
            )
        except Exception:
            logger.exception("audit hook failed")
        return response
