"""One read-only view of an organization across every module. No Flask here.

Every number comes from the database; nothing here calls RunPod, Discord or a source. Agent data
appears only as counts, never content.
"""

import datetime
from typing import cast

from sqlalchemy import func

from core import audit
from modules.accounts.models import AccountGrant
from modules.agents.models import AgentConversation, AgentMemory, AgentPendingAction
from modules.alerts.models import AlertFeed, AlertPost
from modules.auth.models import MachineToken
from modules.compute.models import ComputePod, ComputeSession
from modules.knowledge.models import KnowledgeSource
from modules.organizations import service as organizations
from modules.organizations.models import Organization
from modules.points.models import Points, UserOrganizationMembership
from modules.runpod.models import App, AppDeployment
from modules.storefront.models import Order, Product


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _iso(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value else None


def overview(db, org: Organization) -> dict:
    """Modules, counts, problems and recent activity for one organization."""
    org_id = cast(int, org.id)
    now = _now()
    sections = {
        "members": _members(db, org_id),
        "points": _points(db, org_id, now),
        "storefront": _storefront(db, org_id),
        "compute": _compute(db, org_id, now),
        "alerts": _alerts(db, org_id, now),
        "apps": _apps(db, org_id),
        "knowledge": _knowledge(db, org_id),
        "agents": _agents(db, org_id, now),
        "accounts": _accounts(db, org_id),
        "tokens": _tokens(db, org_id, now),
    }
    entries = audit.list_entries(db, org=cast(str, org.prefix), limit=200)
    return {
        "organization": {"id": org_id, "name": org.name, "prefix": org.prefix},
        "modules": [
            {"name": name, "description": text, "enabled": organizations.module_enabled(org, name)}
            for name, text in organizations.OPTIONAL_MODULES.items()
        ],
        "sections": sections,
        "problems": _problems(sections),
        "activity": [e for e in entries if e.get("source") != "job"][:25],
        "jobs": [e for e in entries if e.get("source") == "job"][:25],
        "generated_at": now.isoformat(),
    }


def _members(db, org_id: int) -> dict:
    total = db.query(UserOrganizationMembership).filter_by(organization_id=org_id).count()
    return {"total": total}


def _points(db, org_id: int, now: datetime.datetime) -> dict:
    total = db.query(func.coalesce(func.sum(Points.points), 0)).filter(Points.organization_id == org_id).scalar()
    since = now - datetime.timedelta(days=30)
    recent = (
        db.query(func.coalesce(func.sum(Points.points), 0))
        .filter(Points.organization_id == org_id, Points.timestamp >= since)
        .scalar()
    )
    return {"total": float(total or 0), "last_30_days": float(recent or 0)}


def _storefront(db, org_id: int) -> dict:
    products = db.query(Product).filter_by(organization_id=org_id).count()
    pending = db.query(Order).filter_by(organization_id=org_id, status="pending").count()
    return {"products": products, "pending_orders": pending}


def _compute(db, org_id: int, now: datetime.datetime) -> dict:
    pods = db.query(ComputePod).filter_by(organization_id=org_id).order_by(ComputePod.name).all()
    upcoming = (
        db.query(ComputeSession)
        .filter(
            ComputeSession.organization_id == org_id,
            ComputeSession.finished.is_(False),
            ComputeSession.stop_at >= now,
        )
        .order_by(ComputeSession.start_at)
        .limit(10)
        .all()
    )
    return {
        "pods": [{"pod_id": p.pod_id, "name": p.name, "public": p.is_public} for p in pods],
        "sessions": [
            {"pod_id": s.pod_id, "title": s.title, "start_at": _iso(s.start_at), "stop_at": _iso(s.stop_at)}
            for s in upcoming
        ],
    }


def _alerts(db, org_id: int, now: datetime.datetime) -> dict:
    feeds = db.query(AlertFeed).filter_by(organization_id=org_id).order_by(AlertFeed.key).all()
    since = now - datetime.timedelta(days=7)
    counts = dict(
        db.query(AlertPost.feed_id, func.count(AlertPost.id))
        .filter(AlertPost.feed_id.in_([f.id for f in feeds]), AlertPost.posted.is_(True), AlertPost.created_at >= since)
        .group_by(AlertPost.feed_id)
        .all()
    )
    return {
        "feeds": [
            {
                "key": f.key,
                "kind": f.kind,
                "enabled": f.enabled,
                "every_hours": f.every_hours,
                "last_run_at": _iso(f.last_run_at),
                "last_error": f.last_error,
                "posted_7_days": counts.get(f.id, 0),
            }
            for f in feeds
        ]
    }


def _apps(db, org_id: int) -> dict:
    apps = db.query(App).filter_by(organization_id=org_id).order_by(App.name).all()
    result = []
    for app in apps:
        latest = db.query(AppDeployment).filter_by(app_id=app.id).order_by(AppDeployment.started_at.desc()).first()
        result.append(
            {
                "name": app.name,
                "repo": app.repo,
                "tag": app.current_tag,
                "status": latest.status if latest else None,
                "deployed_at": _iso(latest.started_at) if latest else None,
                "error": latest.error if latest else None,
            }
        )
    return {"apps": result}


def _knowledge(db, org_id: int) -> dict:
    sources = db.query(KnowledgeSource).filter_by(organization_id=org_id)
    crawled = sources.filter(KnowledgeSource.fetch_every_hours.isnot(None))
    failing = crawled.filter(KnowledgeSource.last_error.isnot(None)).order_by(KnowledgeSource.key).limit(10).all()
    return {
        "sources": sources.count(),
        "crawled": crawled.count(),
        "failing": [{"key": s.key, "url": s.url, "error": (s.last_error or "")[:300]} for s in failing],
    }


def _agents(db, org_id: int, now: datetime.datetime) -> dict:
    conversations = db.query(AgentConversation).filter_by(organization_id=org_id)
    since = now - datetime.timedelta(days=7)
    active = conversations.filter(AgentConversation.updated_at >= since)
    return {
        "conversations": conversations.count(),
        "active_7_days": active.count(),
        "members_7_days": active.with_entities(AgentConversation.discord_id).distinct().count(),
        "memories": db.query(AgentMemory).filter_by(organization_id=org_id).count(),
        "pending_actions": db.query(AgentPendingAction).filter_by(organization_id=org_id, status="pending").count(),
    }


def _accounts(db, org_id: int) -> dict:
    rows = (
        db.query(AccountGrant.provider, func.count(AccountGrant.id))
        .filter(AccountGrant.organization_id == org_id)
        .group_by(AccountGrant.provider)
        .all()
    )
    return {"linked": dict(rows)}


def _tokens(db, org_id: int, now: datetime.datetime) -> dict:
    rows = (
        db.query(MachineToken)
        .filter(MachineToken.organization_id == org_id, MachineToken.revoked_at.is_(None))
        .filter((MachineToken.expires_at.is_(None)) | (MachineToken.expires_at > now))
        .order_by(MachineToken.created_at.desc())
        .all()
    )
    return {
        "tokens": [
            {"name": t.name, "kind": t.kind, "scopes": t.scopes, "last_used_at": _iso(t.last_used_at)}
            for t in rows
            if t.kind != "cli"
        ],
        "cli_tokens": sum(1 for t in rows if t.kind == "cli"),
    }


def _problems(sections: dict) -> list[dict]:
    """Things an officer should look at, from the sections above."""
    problems = []
    for feed in sections["alerts"]["feeds"]:
        if feed["enabled"] and feed["last_error"]:
            problems.append({"module": "alerts", "subject": feed["key"], "message": feed["last_error"]})
    for app in sections["apps"]["apps"]:
        if app["status"] == "failed":
            problems.append({"module": "apps", "subject": app["name"], "message": app["error"] or "Deploy failed"})
    for source in sections["knowledge"]["failing"]:
        problems.append({"module": "knowledge", "subject": source["key"], "message": source["error"]})
    return problems
