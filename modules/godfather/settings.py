"""The org's Godfather settings: the default pod image, kept in Organization.config["godfather"]."""

from typing import cast

from sqlalchemy.orm.attributes import flag_modified

from modules.godfather.base import GodfatherError, checked_image
from modules.organizations.models import Organization

CONFIG_KEY = "godfather"


def _org(db, org_id: int) -> Organization:
    org = db.query(Organization).filter_by(id=org_id).first()
    if org is None:
        raise GodfatherError(f"No organization with id {org_id}", 404)
    return org


def godfather_settings(db, org_id: int, deployment_image: str) -> dict:
    """The org's default pod image, or None, and the deployment default it falls back to."""
    saved = (cast(dict, _org(db, org_id).config) or {}).get(CONFIG_KEY) or {}
    return {"pod_image": saved.get("pod_image"), "deployment_pod_image": deployment_image}


def pod_image(db, org_id: int, deployment_image: str) -> str:
    """The image a new pod gets when the request names none."""
    return godfather_settings(db, org_id, deployment_image)["pod_image"] or deployment_image


def update_godfather_settings(db, org_id: int, data: object, deployment_image: str) -> dict:
    """Set the org's default pod image. null or an empty string goes back to the deployment default. Commits."""
    if not isinstance(data, dict) or set(data) - {"pod_image"}:
        raise GodfatherError("Send an object with pod_image")
    value = cast(dict, data).get("pod_image")
    if value is not None and not isinstance(value, str):
        raise GodfatherError("pod_image must be a string")
    value = (value or "").strip()
    if len(value) > 200 or any(c.isspace() for c in value):
        raise GodfatherError("pod_image must be an image name of at most 200 characters, with no spaces")
    if value:
        checked_image(value)
    org = _org(db, org_id)
    saved = dict(cast(dict, org.config) or {})
    current = {k: v for k, v in (saved.get(CONFIG_KEY) or {}).items() if k != "pod_image"}
    saved[CONFIG_KEY] = current | ({"pod_image": value} if value else {})
    org.config = saved
    flag_modified(org, "config")
    db.commit()
    return godfather_settings(db, org_id, deployment_image)
