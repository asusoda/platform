"""Checks that each API request logs its route, org and credential kind, and never the token."""

import logging


def _lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "request_log"]


def test_logs_access_token_with_org(client, officer_headers, caplog):
    with caplog.at_level(logging.INFO, logger="request_log"):
        client.get("/api/points/soda/users", headers=officer_headers)
    (line,) = _lines(caplog)
    assert "route=/api/points/<string:org_prefix>/users" in line
    assert "org=soda" in line
    assert "credential=access" in line
    assert "discord_id=900000000000000001" in line
    assert officer_headers["Authorization"].split(" ")[1] not in line


def test_logs_app_token_as_app(client, caplog):
    from shared import tokenManager

    token = tokenManager.generate_app_token("ci", "website")
    with caplog.at_level(logging.INFO, logger="request_log"):
        client.get("/api/points/soda/users", headers={"Authorization": f"Bearer {token}"})
    (line,) = _lines(caplog)
    assert "credential=app" in line
    assert token not in line


def test_logs_external_token_and_origin(client, clerk_headers, caplog):
    with caplog.at_level(logging.INFO, logger="request_log"):
        client.get(
            "/api/storefront/soda/wallet/alice@asu.edu",
            headers={**clerk_headers, "Origin": "https://thesoda.io"},
        )
    (line,) = _lines(caplog)
    assert "credential=external" in line
    assert "origin=thesoda.io" in line


def test_skips_health(client, caplog):
    with caplog.at_level(logging.INFO, logger="request_log"):
        client.get("/health")
    assert _lines(caplog) == []
