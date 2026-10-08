"""Source packs: named sets of crawled sources that a module adds to an org in one step. No Flask here.

A module registers a pack when it is imported. Each pack owns the sources whose keys start with its
key prefix. Syncing a pack adds or updates those sources; the crawl job then fetches them.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func

from modules.knowledge.models import KnowledgeSource
from modules.knowledge.service import KnowledgeError


@dataclass(frozen=True)
class Pack:
    name: str
    title: str
    description: str
    key_prefix: str
    # sync(db, org_id, org_prefix) returns {"added", "updated", "retired"} and commits
    sync: Callable[..., dict]


PACKS: dict[str, Pack] = {}


def register(pack: Pack) -> None:
    PACKS[pack.name] = pack


def list_packs(db, org_id: int) -> list[dict]:
    """Every registered pack with the number of the org's sources it owns."""
    result = []
    for pack in sorted(PACKS.values(), key=lambda p: p.name):
        count = (
            db.query(func.count(KnowledgeSource.id))
            .filter(
                KnowledgeSource.organization_id == org_id,
                KnowledgeSource.key.like(pack.key_prefix + "%"),
                KnowledgeSource.enabled.is_(True),
            )
            .scalar()
        )
        result.append(
            {
                "name": pack.name,
                "title": pack.title,
                "description": pack.description,
                "key_prefix": pack.key_prefix,
                "sources": int(count or 0),
            }
        )
    return result


def sync(db, org_id: int, org_prefix: str, name: str) -> dict:
    pack = PACKS.get(name)
    if pack is None:
        raise KnowledgeError(f"No source pack named {name}", 404)
    return pack.sync(db, org_id, org_prefix)
