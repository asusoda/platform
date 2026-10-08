"""Agent turns: one context read and one atomic commit, for members Discord says are in the org."""

import random
import uuid

import pytest

from core.discord_directory import DiscordUnavailable
from tests.contract.conftest import FakeBot


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="sparky", kind="agent", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def agent(app):
    return _issue("soda", "agents:read", "agents:write")


@pytest.fixture
def member():
    return f"/api/agents/members/{random.randint(10**17, 10**18)}"


def _turn(cid, **extra):
    return {"conversation_id": cid, "channel_id": "chan-1", "visibility": "private", **extra}


def test_commit_then_context(client, agent, member):
    cid = str(uuid.uuid4())
    token = str(uuid.uuid4())
    body = _turn(
        cid,
        messages=[{"role": "user", "content": "I take CSE 310"}, {"role": "assistant", "content": "Noted."}],
        memories=[{"kind": "semantic", "content": "Takes CSE 310", "confidence": 0.9}],
        facts=[
            {
                "subject": {"kind": "person", "label": "me"},
                "relation": "takes",
                "object": {"kind": "course", "label": "CSE 310"},
                "confidence": 0.8,
            }
        ],
        pending=[{"token": token, "action": {"tool": "canvas.submit"}, "payload_hash": "abc"}],
    )
    response = client.post(f"{member}/turn/commit", json=body, headers=agent)
    assert response.status_code == 201, response.get_json()
    result = response.get_json()
    assert result["conversation_id"] == cid and len(result["seqs"]) == 2
    assert len(result["memory_ids"]) == 1 and result["facts"] == 1 and result["pending"] == 1

    context = client.post(f"{member}/turn/context", json=_turn(cid), headers=agent).get_json()
    assert context["member"]["display_name"] == "officer" and context["member"]["officer"] is True
    assert context["conversation"] == {"id": cid, "owned": True}
    assert [m["content"] for m in context["messages"]] == ["I take CSE 310", "Noted."]
    assert context["memories"][0]["content"] == "Takes CSE 310"
    assert context["profile"]["relations"][0]["relation"] == "takes"

    claimed = client.post(f"{member}/pending/{token}/claim", json={"approved": True}, headers=agent)
    assert claimed.get_json()["action"] == {"tool": "canvas.submit"}


def test_summary_and_limits(client, agent, member):
    cid = str(uuid.uuid4())
    seqs = client.post(
        f"{member}/turn/commit",
        json=_turn(cid, messages=[{"role": "user", "content": f"m{i}"} for i in range(3)]),
        headers=agent,
    ).get_json()["seqs"]
    client.post(
        f"{member}/turn/commit",
        json=_turn(cid, summary={"content": "first two", "covers": seqs[1]}),
        headers=agent,
    )
    context = client.post(
        f"{member}/turn/context", json=_turn(cid, memory_limit=0, profile_limit=0), headers=agent
    ).get_json()
    assert [m["role"] for m in context["messages"]] == ["summary", "user"]
    assert context["memories"] == [] and context["profile"] == {"nodes": [], "relations": []}


def test_a_bad_part_writes_nothing(client, agent, member):
    cid = str(uuid.uuid4())
    body = _turn(
        cid,
        messages=[{"role": "user", "content": "hello"}],
        memories=[{"kind": "not-a-kind", "content": "x"}],
    )
    assert client.post(f"{member}/turn/commit", json=body, headers=agent).status_code == 400
    context = client.post(f"{member}/turn/context", json=_turn(cid), headers=agent).get_json()
    assert context["conversation"]["owned"] is False and context["messages"] == []
    assert client.post(f"{member}/turn/commit", json=_turn(cid), headers=agent).status_code == 400


def test_another_members_conversation_is_refused(client, agent, member):
    cid = str(uuid.uuid4())
    client.post(f"{member}/turn/commit", json=_turn(cid, messages=[{"role": "user", "content": "a"}]), headers=agent)
    other = f"/api/agents/members/{random.randint(10**17, 10**18)}"
    body = _turn(cid, messages=[{"role": "user", "content": "b"}])
    assert client.post(f"{other}/turn/commit", json=body, headers=agent).status_code == 409
    context = client.post(f"{other}/turn/context", json=_turn(cid), headers=agent).get_json()
    assert context["conversation"]["owned"] is False and context["messages"] == []


class _NotInServer(FakeBot):
    def get_member(self, guild_id, user_id):
        return None


class _Down(FakeBot):
    def get_member(self, guild_id, user_id):
        raise DiscordUnavailable("down")


@pytest.mark.parametrize(("directory", "status"), [(_NotInServer(), 403), (_Down(), 503), (None, 503)])
def test_membership_is_checked(client, agent, member, monkeypatch, app, directory, status):
    monkeypatch.setattr(app, "discord_directory", directory)
    cid = str(uuid.uuid4())
    assert client.post(f"{member}/turn/context", json=_turn(cid), headers=agent).status_code == status
    body = _turn(cid, messages=[{"role": "user", "content": "a"}])
    assert client.post(f"{member}/turn/commit", json=body, headers=agent).status_code == status


def test_scopes(client, member):
    reader = _issue("soda", "agents:read")
    cid = str(uuid.uuid4())
    body = _turn(cid, messages=[{"role": "user", "content": "a"}])
    assert client.post(f"{member}/turn/commit", json=body, headers=reader).status_code == 403
    assert client.post(f"{member}/turn/context", json=_turn(cid), headers=reader).status_code == 200
