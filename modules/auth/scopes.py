"""Scopes a machine token can hold. Modules declare the scopes their tools and endpoints check."""

SCOPES: dict[str, str] = {}


def declare(name: str, description: str) -> None:
    SCOPES[name] = description
