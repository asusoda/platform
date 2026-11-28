"""Registers the ASU sign-in as asu, which the clubs and club_events live queries of the asu content read with."""

from modules.knowledge.content import signins


def _usable(db, org_id: int) -> bool:
    from modules.knowledge.submodules.asu_signin import service

    return service.usable(db, org_id)


def _read(db, org_id: int, org_prefix: str, url: str):
    from modules.knowledge.submodules.asu_signin import service

    return service.read(db, org_id, org_prefix, url)


signins.register("asu", _usable, _read)
