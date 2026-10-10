"""Revocations and app tokens live in the database, so they hold across restarts and processes."""

from tests.contract.conftest import OFFICER_DISCORD_ID


def test_revoked_access_token_stays_revoked_after_restart(app):
    from modules.auth.tokens import token_manager

    token = token_manager.generate_token(username="revoked-officer", discord_id=OFFICER_DISCORD_ID)
    token_manager.delete_token(token)
    token_manager.blacklist.clear()  # what a restart or another process starts with
    assert not token_manager.is_token_valid(token)


def test_officer_lists_and_revokes_app_token(client, officer_headers):
    from modules.auth.tokens import token_manager

    token = token_manager.generate_app_token("officer", "scoreboard", OFFICER_DISCORD_ID)
    app_headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/points/soda/users", headers=app_headers).status_code == 200

    listed = client.get("/api/auth/appTokens", headers=officer_headers).get_json()
    (entry,) = [t for t in listed if t["app_name"] == "scoreboard"]
    assert client.delete(f"/api/auth/appTokens/{entry['id']}", headers=officer_headers).status_code == 200

    assert client.get("/api/points/soda/users", headers=app_headers).status_code == 401


def test_cannot_revoke_another_officers_app_token(client):
    from modules.auth.tokens import token_manager

    token_manager.generate_app_token("other", "theirs", "900000000000000077")
    other_headers = {
        "Authorization": f"Bearer {token_manager.generate_token(username='x', discord_id='900000000000000078')}"
    }
    listed = client.get("/api/auth/appTokens", headers=other_headers).get_json()
    assert listed == []
    assert client.delete("/api/auth/appTokens/9999", headers=other_headers).status_code == 404
