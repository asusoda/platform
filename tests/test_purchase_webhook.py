"""Tests for the storefront purchase Discord webhook notification."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def _temporary_storefront_import_stubs():
    """Temporarily stub modules that trigger heavy side-effects on import."""
    import sys
    import types

    fake_shared = types.ModuleType("shared")
    fake_shared.config = MagicMock()  # type: ignore[attr-defined]
    fake_shared.tokenManager = MagicMock()  # type: ignore[attr-defined]
    fake_decoraters = types.ModuleType("modules.auth.decoraters")
    for name in ("auth_required", "dual_auth_required", "error_handler", "member_required"):
        setattr(fake_decoraters, name, lambda f: f)
    fake_db = types.ModuleType("modules.utils.db")
    fake_db.DBConnect = MagicMock  # type: ignore[attr-defined]

    replacements = {
        "shared": fake_shared,
        "modules.auth.decoraters": fake_decoraters,
        "modules.utils.db": fake_db,
    }
    originals = {name: sys.modules.get(name) for name in replacements}
    try:
        for name, module in replacements.items():
            sys.modules[name] = module
        yield
    finally:
        for name, original in originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def _make_send_purchase_webhook():
    """Create a standalone version of send_purchase_webhook for testing."""
    import importlib
    import sys

    original_storefront_api = sys.modules.get("modules.storefront.api")
    with _temporary_storefront_import_stubs():
        mod = importlib.import_module("modules.storefront.api")
        send_webhook = mod.send_purchase_webhook

    if original_storefront_api is None:
        sys.modules.pop("modules.storefront.api", None)
    else:
        sys.modules["modules.storefront.api"] = original_storefront_api

    return send_webhook


send_purchase_webhook = _make_send_purchase_webhook()


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

        webhook_thread = send_purchase_webhook(42, "buyer@example.com", items, 110, "TestOrg")
        webhook_thread.join(timeout=5)
        assert webhook_thread.name == "storefront-purchase-webhook"  # nosec B101

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1]["json"]

        assert len(payload["embeds"]) == 1  # nosec B101
        embed = payload["embeds"][0]
        assert "New Storefront Purchase" in embed["title"]  # nosec B101

        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert fields["Order"] == "#42"  # nosec B101
        assert fields["Buyer"] == "buyer@example.com"  # nosec B101
        assert fields["Organization"] == "TestOrg"  # nosec B101
        assert "T-Shirt" in fields["Items"]  # nosec B101
        assert "Sticker" in fields["Items"]  # nosec B101
        assert "110" in fields["Total"]  # nosec B101

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {"DISCORD_STORE_WEBHOOK_URL": ""})
    def test_webhook_skipped_when_url_not_configured(self, mock_post):
        """Webhook should not fire when DISCORD_STORE_WEBHOOK_URL is empty."""
        webhook_thread = send_purchase_webhook(1, "user@example.com", [], 0, "Org")
        webhook_thread.join(timeout=5)

        mock_post.assert_not_called()

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {"DISCORD_STORE_WEBHOOK_URL": "https://discord.com/api/webhooks/test"})
    def test_webhook_does_not_raise_on_http_error(self, mock_post):
        """Webhook failures should be logged, not raised."""
        mock_post.side_effect = Exception("connection error")

        # Should not raise
        webhook_thread = send_purchase_webhook(
            1, "user@example.com", [{"name": "Hat", "quantity": 1, "price": 20}], 20, "Org"
        )
        webhook_thread.join(timeout=5)

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {}, clear=False)
    def test_webhook_skipped_when_env_var_missing(self, mock_post):
        """Webhook should not fire when env var is not set at all."""
        import os

        os.environ.pop("DISCORD_STORE_WEBHOOK_URL", None)

        webhook_thread = send_purchase_webhook(1, "user@example.com", [], 0, "Org")
        webhook_thread.join(timeout=5)

        mock_post.assert_not_called()

    @patch("modules.storefront.api.http_requests.post")
    @patch.dict("os.environ", {"DISCORD_STORE_WEBHOOK_URL": "https://discord.com/api/webhooks/test"})
    def test_items_field_is_truncated_to_discord_limit(self, mock_post):
        """Item field should stay within Discord's 1024 char embed field limit."""
        mock_post.return_value = MagicMock(status_code=204)

        long_name = "A" * 500
        items = [
            {"name": long_name, "quantity": 1, "price": 10},
            {"name": long_name, "quantity": 2, "price": 20},
            {"name": long_name, "quantity": 3, "price": 30},
        ]

        webhook_thread = send_purchase_webhook(99, "buyer@example.com", items, 60, "TestOrg")
        webhook_thread.join(timeout=5)

        payload = mock_post.call_args.kwargs["json"]
        fields = {f["name"]: f["value"] for f in payload["embeds"][0]["fields"]}
        assert len(fields["Items"]) <= 1024  # nosec B101
