"""What each hosting service file uses: the error, the provider and client of an app, and app lookup. No Flask here."""

import json

from core import hosting
from core.errors import ServiceError
from hosting.models import App

# The provider name of This server
SERVER = "server"


class AppError(ServiceError, ValueError):
    pass


def provider(name: object) -> hosting.HostingProvider:
    """The provider of this name. Raises AppError 400 for an unknown name."""
    try:
        return hosting.get(name)
    except hosting.ProviderError as e:
        raise AppError(e.message, e.status) from e


def provider_of(app: App) -> hosting.HostingProvider:
    return provider(str(app.provider or hosting.DEFAULT))


def client_for(db, org_id: int | None, name: str = hosting.DEFAULT) -> hosting.HostingClient:
    """The org's client of the provider. Raises AppError 503 when the org has not connected it."""
    found = provider(name)
    if not found.configured(db, org_id):
        raise AppError(f"Connect {found.title} on the Integrations page to deploy there", 503)
    return found.client(db, org_id)


def find(db, org_id: int | None, name: str) -> App:
    app = db.query(App).filter_by(organization_id=org_id, name=name).first()
    if app is None:
        raise AppError("No app with this name", 404)
    return app


def manifest_of(app: App) -> dict:
    return json.loads(str(app.manifest))
