"""HTTP routes for agents (machine tokens) and for members managing their own agent data.

Agent routes take a machine token with agents:read or agents:write and name the member by Discord
id; the organization is the token's. Member routes take a signed-in Discord session. Officers and
superadmins have no route to read agent data.
"""

from flask import Blueprint, g, jsonify, request

from core.db import db_connect
from core.http import audit_hook
from modules.auth.decoraters import machine_scope_required, member_required
from modules.auth.routes import INACTIVE_ORG, json_body, token_org
from modules.knowledge import embedder
from modules.organizations.models import Organization

from . import service, turns

agents_blueprint = Blueprint("agents", __name__)

M = "/members/<string:discord_id>"

# Per-turn writes; recording each would flood the audit log. Deletes and confirmations are recorded.
audit_hook.SKIPPED_ROUTES.update(
    {
        f"/api/agents{M}/conversations/<string:conversation_id>",
        f"/api/agents{M}/conversations/<string:conversation_id>/messages",
        f"/api/agents{M}/conversations/<string:conversation_id>/summary",
        f"/api/agents{M}/channels/<string:channel_id>/end",
        f"/api/agents{M}/memories",
        f"/api/agents{M}/profile/facts",
        f"/api/agents{M}/pending/<string:token>",
        f"/api/agents{M}/turn/context",
        f"/api/agents{M}/turn/commit",
    }
)


def _error(e: service.AgentError):
    return jsonify({"error": e.message}), e.status


def _agent_route(rule: str, scope: str, methods: list[str]):
    """Register a machine route. The view gets (db, who, **path args) and returns a JSON-able value or a response."""

    def decorator(view):
        def wrapper(discord_id, **kwargs):
            caller = g.machine_caller
            db = db_connect.SessionLocal()
            try:
                if token_org(db) is None:
                    return jsonify({"error": INACTIVE_ORG}), 403
                who = service.owner(caller.organization_id, discord_id, caller.token_id)
                result = view(db, who, **kwargs)
                return result if isinstance(result, tuple) else jsonify(result)
            except service.AgentError as e:
                db.rollback()
                return _error(e)
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        agents_blueprint.route(M + rule, methods=methods)(machine_scope_required(scope)(wrapper))
        return view

    return decorator


def _int_arg(name: str) -> int | None:
    value = request.args.get(name)
    if value is None:
        return None
    if not value.isdigit():
        raise service.AgentError(f"{name} must be a positive integer")
    return int(value)


# Conversations


@_agent_route("/conversations/<string:conversation_id>", "agents:write", ["PUT"])
def ensure_conversation(db, who, conversation_id):
    data = json_body()
    cid = service.ensure(db, who, conversation_id, data.get("channel_id"), data.get("visibility", "public"))
    return {"id": cid}


@_agent_route("/conversations/<string:conversation_id>", "agents:read", ["GET"])
def get_conversation(db, who, conversation_id):
    visibility = request.args.get("visibility", "public")
    return {"owned": service.owns(db, who, conversation_id, visibility)}


@_agent_route("/conversations/<string:conversation_id>/messages", "agents:read", ["GET"])
def load_messages(db, who, conversation_id):
    return {"messages": service.load(db, who, conversation_id, _int_arg("limit"))}


@_agent_route("/conversations/<string:conversation_id>/messages", "agents:write", ["POST"])
def append_messages(db, who, conversation_id):
    return {"seqs": service.append(db, who, conversation_id, json_body().get("messages"))}, 201


@_agent_route("/conversations/<string:conversation_id>/summary", "agents:write", ["POST"])
def append_summary(db, who, conversation_id):
    data = json_body()
    return {"seq": service.append_summary(db, who, conversation_id, data.get("content"), data.get("covers"))}, 201


@_agent_route("/channels/<string:channel_id>/latest", "agents:read", ["GET"])
def latest_conversation(db, who, channel_id):
    return {"id": service.latest(db, who, channel_id, request.args.get("visibility", "public"))}


@_agent_route("/channels/<string:channel_id>/end", "agents:write", ["POST"])
def end_conversations(db, who, channel_id):
    return {"ended": service.end(db, who, channel_id)}


# Memories


@_agent_route("/memories", "agents:read", ["GET"])
def recall_memories(db, who):
    kinds = request.args.get("kinds")
    return {"memories": service.recall(db, who, kinds.split(",") if kinds else None, _int_arg("limit"))}


@_agent_route("/memories", "agents:write", ["POST"])
def write_memory(db, who):
    data = json_body()
    memory = service.remember(
        db,
        who,
        kind=data.get("kind"),
        content=data.get("content"),
        sensitivity=data.get("sensitivity", "normal"),
        confidence=data.get("confidence"),
        source_seq=data.get("source_seq"),
        expires_in_days=data.get("expires_in_days"),
    )
    return memory, 201


@_agent_route("/memories/<string:memory_id>", "agents:write", ["DELETE"])
def delete_memory(db, who, memory_id):
    return {"deleted": service.forget_memory(db, who, memory_id)}


# Profile graph


@_agent_route("/profile", "agents:read", ["GET"])
def read_profile(db, who):
    limit = _int_arg("limit")
    return {"nodes": service.profile_nodes(db, who, limit), "relations": service.relations(db, who, limit)}


@_agent_route("/profile/facts", "agents:write", ["POST"])
def upsert_facts(db, who):
    return {"stored": service.upsert(db, who, json_body().get("facts"), embedder=embedder.configured())}


@_agent_route("/profile/similar", "agents:read", ["GET"])
def similar_nodes(db, who):
    nodes = service.similar(db, who, request.args.get("text"), _int_arg("limit"), embedder.configured())
    return {"nodes": nodes}


@_agent_route("/profile/matching", "agents:read", ["GET"])
def matching_relations(db, who):
    return {"relations": service.matching(db, who, request.args.get("subject"), request.args.get("relation"))}


@_agent_route("/profile/relations", "agents:write", ["DELETE"])
def drop_relation(db, who):
    data = json_body()
    return {"deleted": service.drop_relation(db, who, data.get("subject"), data.get("relation"), data.get("object"))}


@_agent_route("/profile/nodes", "agents:write", ["DELETE"])
def forget_label(db, who):
    return {"deleted": service.forget(db, who, request.args.get("label"))}


@_agent_route("/data", "agents:write", ["DELETE"])
def forget_member(db, who):
    """The member asked the agent to forget them: profile graph and memories."""
    return {"deleted": service.forget_all(db, who)}


# Pending actions


@_agent_route("/pending/<string:token>", "agents:write", ["PUT"])
def hold_action(db, who, token):
    data = json_body()
    service.hold(db, who, token, data.get("action"), data.get("payload_hash"), data.get("ttl_seconds", 600))
    return {"held": True}, 201


@_agent_route("/pending/<string:token>/claim", "agents:write", ["POST"])
def claim_action(db, who, token):
    claimed = service.claim(db, who, token, json_body().get("approved"))
    if claimed is None:
        return jsonify({"error": "No pending action for this token"}), 404
    return claimed


# Turns: one read before the model call, one write after the answer


def _member_info(db, who):
    """The member as Discord sees them in the token's org. Raises AgentError when they are not in it."""
    from modules.auth.access import discord_directory

    org = db.query(Organization).filter_by(id=who.organization_id).one()
    return turns.member(discord_directory(), org.guild_id, org.officer_role_id, who.discord_id)


@_agent_route("/turn/context", "agents:read", ["POST"])
def turn_context(db, who):
    return turns.context(db, who, _member_info(db, who), json_body(), embedder.configured())


@_agent_route("/turn/commit", "agents:write", ["POST"])
def turn_commit(db, who):
    _member_info(db, who)
    return turns.commit(db, who, json_body(), embedder.configured()), 201


# Member self-service: a member sees and deletes what agents keep about them.


def _member(organization, user_discord_id):
    return service.owner(int(organization.id), str(user_discord_id))


def _member_view(view):
    def wrapper(org_prefix, user_discord_id=None, organization=None, **kwargs):
        db = db_connect.SessionLocal()
        try:
            return view(db, _member(organization, user_discord_id), **kwargs)
        except service.AgentError as e:
            db.rollback()
            return _error(e)
        finally:
            db.close()

    wrapper.__name__ = view.__name__
    return member_required(wrapper)


@agents_blueprint.route("/<string:org_prefix>/me", methods=["GET"])
@_member_view
def my_agent_data(db, who):
    return jsonify(
        {
            "conversations": service.list_conversations(db, who),
            "memories": service.recall(db, who, limit=service.MAX_LIMIT),
            "profile": {"nodes": service.profile_nodes(db, who, 500), "relations": service.relations(db, who, 500)},
        }
    )


@agents_blueprint.route("/<string:org_prefix>/me/conversations/<string:conversation_id>", methods=["DELETE"])
@_member_view
def delete_my_conversation(db, who, conversation_id):
    if not service.delete_conversation(db, who, conversation_id):
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify({"deleted": True})


@agents_blueprint.route("/<string:org_prefix>/me", methods=["DELETE"])
@_member_view
def delete_my_agent_data(db, who):
    """Everything agents keep about the member in this org: conversations, memories, profile."""
    return jsonify({"deleted": service.forget_everything(db, who)})
