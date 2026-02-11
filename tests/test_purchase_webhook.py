"""Tests for the storefront purchase Discord webhook notification."""

import threading
from unittest.mock import MagicMock, patch


def _make_send_purchase_webhook():
    """Create a standalone version of send_purchase_webhook for testing,
    avoiding the heavy import chain through shared.py / DBConnect."""
    import importlib
    import sys
    import types

    # Provide lightweight stubs for modules that trigger heavy side-effects
    fake_shared = types.ModuleType("shared")
    fake_shared.config = MagicMock()  # type: ignore[attr-defined]
    fake_shared.tokenManager = MagicMock()  # type: ignore[attr-defined]
    sys.modules.setdefault("shared", fake_shared)

    fake_decoraters = types.ModuleType("modules.auth.decoraters")
    for name in ("auth_required", "dual_auth_required", "error_handler", "member_required"):
        setattr(fake_decoraters, name, lambda f: f)
    sys.modules.setdefault("modules.auth.decoraters", fake_decoraters)

    fake_db = types.ModuleType("modules.utils.db")
    fake_db.DBConnect = MagicMock  # type: ignore[attr-defined]
    sys.modules.setdefault("modules.utils.db", fake_db)

    mod = importlib.import_module("modules.storefront.api")
    return mod.send_purchase_webhook


send_purchase_webhook = _make_send_purchase_webhook()


def _wait_for_daemon_threads():
    for t in threading.enumerate():
        if t.daemon and t.name != "MainThread":
            t.join(timeout=5)


class TestSendPurchaseWebhook:
    """Tests for the send_purchase_webhook helper function."""

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {"DISCORD_STORE_WEBHOOK_URL": "https://discord.com/api/webhooks/test"})
    def test_webhook_sends_correct_payload(self, mock_post):
        """Webhook should POST a Discord embed with order details."""
        mock_post.return_value = MagicMock(status_code=204)

        items = [
            {"name": "T-Shirt", "quantity": 2, "price": 50},
            {"name": "Sticker", "quantity": 1, "price": 10},
        ]

        send_purchase_webhook(42, "buyer@example.com", items, 110, "TestOrg")
        _wait_for_daemon_threads()

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]

        assert len(payload["embeds"]) == 1
        embed = payload["embeds"][0]
        assert "New Storefront Purchase" in embed["title"]

        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert fields["Order"] == "#42"
        assert fields["Buyer"] == "buyer@example.com"
        assert fields["Organization"] == "TestOrg"
        assert "T-Shirt" in fields["Items"]
        assert "Sticker" in fields["Items"]
        assert "110" in fields["Total"]

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {"DISCORD_STORE_WEBHOOK_URL": ""})
    def test_webhook_skipped_when_url_not_configured(self, mock_post):
        """Webhook should not fire when DISCORD_STORE_WEBHOOK_URL is empty."""
        send_purchase_webhook(1, "user@example.com", [], 0, "Org")
        _wait_for_daemon_threads()

        mock_post.assert_not_called()

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {"DISCORD_STORE_WEBHOOK_URL": "https://discord.com/api/webhooks/test"})
    def test_webhook_does_not_raise_on_http_error(self, mock_post):
        """Webhook failures should be logged, not raised."""
        mock_post.side_effect = Exception("connection error")

        # Should not raise
        send_purchase_webhook(1, "user@example.com", [{"name": "Hat", "quantity": 1, "price": 20}], 20, "Org")
        _wait_for_daemon_threads()

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {}, clear=False)
    def test_webhook_skipped_when_env_var_missing(self, mock_post):
        """Webhook should not fire when env var is not set at all."""
        import os

        os.environ.pop("DISCORD_STORE_WEBHOOK_URL", None)

        send_purchase_webhook(1, "user@example.com", [], 0, "Org")
        _wait_for_daemon_threads()

        mock_post.assert_not_called()
