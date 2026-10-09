"""Scopes a machine token can hold. Modules declare the scopes their tools and endpoints check.

A scope with an integration gives tools of that connected service, such as github:read. The Tokens page
groups those scopes under the integration. A scope with uses reaches those integrations through Platform,
such as knowledge:read, which embeds the query with the org's embeddings key. The Tokens page marks them.
"""

SCOPES: dict[str, str] = {}
INTEGRATION_SCOPES: dict[str, str] = {}
SCOPE_USES: dict[str, tuple[str, ...]] = {}


def declare(name: str, description: str, integration: str | None = None, uses: tuple[str, ...] = ()) -> None:
    SCOPES[name] = description
    if integration is not None:
        INTEGRATION_SCOPES[name] = integration
    if uses:
        SCOPE_USES[name] = uses
