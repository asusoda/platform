"""Scopes a machine token can hold. Modules declare the scopes their tools and endpoints check.

A scope with an integration gives tools of that connected service, such as github:read. The Tokens page
groups those scopes under the integration.
"""

SCOPES: dict[str, str] = {}
INTEGRATION_SCOPES: dict[str, str] = {}


def declare(name: str, description: str, integration: str | None = None) -> None:
    SCOPES[name] = description
    if integration is not None:
        INTEGRATION_SCOPES[name] = integration
