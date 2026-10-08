"""The flask CLI: org setup, module switches, jobs, config check."""

import pytest


@pytest.fixture
def cli(app):
    return app.test_cli_runner()


@pytest.fixture
def remove_org(app):
    prefixes = []
    yield prefixes.append
    from modules.organizations.models import Organization
    from shared import db_connect

    db = db_connect.SessionLocal()
    try:
        db.query(Organization).filter(Organization.prefix.in_(prefixes)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_org_create_with_modules_off(cli, client, remove_org):
    remove_org("clitest")
    result = cli.invoke(
        args=[
            "org",
            "create",
            "--name",
            "CLI Club",
            "--prefix",
            "clitest",
            "--guild-id",
            "1009",
            "--off",
            "points,storefront",
        ]
    )
    assert result.exit_code == 0, result.output
    assert "points=off" in result.output and "calendar=on" in result.output
    assert client.get("/api/storefront/clitest/products").status_code == 404


@pytest.mark.parametrize(
    "args,message",
    [
        (["--prefix", "soda", "--guild-id", "1010"], "taken"),
        (["--prefix", "Bad Prefix", "--guild-id", "1010"], "Prefix must be"),
        (["--prefix", "newone", "--guild-id", "1001"], "already has"),
        (["--prefix", "newone", "--guild-id", "1010", "--off", "auth"], "Unknown or required"),
    ],
)
def test_org_create_refuses_bad_input(cli, args, message):
    result = cli.invoke(args=["org", "create", "--name", "X", *args])
    assert result.exit_code != 0
    assert message in result.output


def test_org_modules_switches(cli, restore_soda_config):
    result = cli.invoke(args=["org", "modules", "soda", "--off", "calendar"])
    assert result.exit_code == 0, result.output
    assert "calendar=off" in result.output
    assert "calendar=on" in cli.invoke(args=["org", "modules", "soda", "--on", "calendar"]).output


def test_jobs_list_and_run(cli):
    listing = cli.invoke(args=["jobs", "list"])
    assert "auth.cleanup_tokens" in listing.output
    result = cli.invoke(args=["jobs", "run", "auth.cleanup_tokens"])
    assert result.exit_code == 0, result.output
    assert cli.invoke(args=["jobs", "run", "nope"]).exit_code != 0


def test_config_check_reports_missing_settings(cli, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    result = cli.invoke(args=["config", "check"])
    assert "FAIL  BOT_TOKEN missing" in result.output
    assert "database reachable" in result.output
    assert result.exit_code != 0
