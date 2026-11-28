"""Status codes and bodies of the store routes, kept the same when their logic moved to service.py."""

import pytest

from tests.contract.conftest import MEMBER_EMAIL


@pytest.fixture
def remove_route_products(app):
    yield
    from core.db import db_connect
    from modules.points.submodules.store.models import Product

    with db_connect.SessionLocal() as db:
        db.query(Product).filter(Product.name.like("Route test%")).delete(synchronize_session=False)
        db.commit()


def _json(response):
    return response.status_code, response.get_json()


def test_product_create_update_delete(client, officer_headers, remove_route_products):
    base = "/api/storefront/soda/products"
    status, body = _json(
        client.post(base, json={"name": "Route test", "price": 3, "stock": 2}, headers=officer_headers)
    )
    assert (status, body["message"]) == (201, "Product created successfully")
    product_id = body["id"]
    assert body["product"]["id"] == product_id
    assert set(body["product"]) == {
        "id",
        "name",
        "description",
        "price",
        "stock",
        "image_url",
        "category",
        "organization_id",
    }

    status, body = _json(client.get(f"{base}/{product_id}"))
    assert (status, body["name"], body["price"]) == (200, "Route test", 3)
    assert {"created_at", "updated_at", "category"} <= set(body)

    status, body = _json(client.put(f"{base}/{product_id}", json={"stock": 0}, headers=officer_headers))
    assert (status, body["message"], body["product"]["stock"]) == (200, "Product updated successfully", 0)
    assert all(p["id"] != product_id for p in client.get("/api/storefront/soda/store").get_json()["products"])

    assert _json(client.delete(f"{base}/{product_id}", headers=officer_headers)) == (
        200,
        {"message": "Product deleted successfully"},
    )
    missing = (404, {"error": "Product not found"})
    assert _json(client.get(f"{base}/{product_id}")) == missing
    assert _json(client.put(f"{base}/{product_id}", json={"stock": 1}, headers=officer_headers)) == missing
    assert _json(client.delete(f"{base}/{product_id}", headers=officer_headers)) == missing


def test_product_refusals(client, officer_headers):
    base = "/api/storefront/soda/products"
    assert _json(client.post(base, json={"price": 1, "stock": 1}, headers=officer_headers)) == (
        400,
        {"error": "Product name is required"},
    )
    assert _json(client.post(base, json={"name": "x", "stock": 1}, headers=officer_headers)) == (
        400,
        {"error": "Product price is required"},
    )
    assert _json(client.post(base, json={"name": "x", "price": 1}, headers=officer_headers)) == (
        400,
        {"error": "Product stock is required"},
    )
    assert _json(client.post(base, json={"name": "x", "price": 1, "stock": 0}, headers=officer_headers)) == (
        400,
        {"error": "Product stock is required"},
    )
    # The sticker of the seed has an order
    sticker = client.get(base).get_json()[0]["id"]
    status, body = _json(client.delete(f"{base}/{sticker}", headers=officer_headers))
    assert status == 409


def test_unknown_org(client, officer_headers, clerk_headers):
    missing = (404, {"error": "Organization not found"})
    assert _json(client.get("/api/storefront/nope/products")) == missing
    assert _json(client.get("/api/storefront/nope/products/1")) == missing
    assert _json(client.get("/api/storefront/nope/store")) == missing
    assert _json(client.get("/api/storefront/nope/orders/1", headers=officer_headers)) == missing
    assert _json(client.delete("/api/storefront/nope/orders/1", headers=officer_headers)) == missing
    assert _json(client.get(f"/api/storefront/nope/wallet/{MEMBER_EMAIL}", headers=clerk_headers)) == missing


def test_order_detail(client, officer_headers):
    orders = client.get("/api/storefront/soda/orders", headers=officer_headers).get_json()
    order_id = orders[0]["id"]
    status, body = _json(client.get(f"/api/storefront/soda/orders/{order_id}", headers=officer_headers))
    assert status == 200
    assert set(body) == {
        "id",
        "user_id",
        "total_amount",
        "status",
        "created_at",
        "updated_at",
        "organization_id",
        "items",
    }
    assert _json(client.get("/api/storefront/soda/orders/999999", headers=officer_headers)) == (
        404,
        {"error": "Order not found"},
    )
    assert _json(client.put("/api/storefront/soda/orders/999999", json={}, headers=officer_headers)) == (
        404,
        {"error": "Order not found"},
    )
    status, body = _json(
        client.put(f"/api/storefront/soda/orders/{order_id}", json={"status": "lost"}, headers=officer_headers)
    )
    assert status == 400
    assert body["error"].startswith("Invalid status")


def test_public_store(client):
    status, body = _json(client.get("/api/storefront/soda/store"))
    assert status == 200
    assert set(body) == {"organization", "products"}
    assert set(body["organization"]) == {"name", "prefix", "description"}
    assert all(set(p) == {"id", "name", "description", "price", "stock", "image_url"} for p in body["products"])


def test_member_points(member_client):
    status, body = _json(member_client.get("/api/storefront/soda/members/points"))
    assert status == 200
    assert body["email"] == MEMBER_EMAIL
    assert isinstance(body["total_points"], int | float)
    assert all(set(p) == {"points", "event", "timestamp", "awarded_by"} for p in body["points_breakdown"])
    assert _json(member_client.get("/api/storefront/soda/members/orders/999999")) == (404, {"error": "Order not found"})


def test_order_refusals(client, clerk_headers, member_client):
    for path in ("/api/storefront/soda/checkout", "/api/storefront/soda/orders"):
        assert _json(client.post(path, json={"items": [{}]}, headers=clerk_headers)) == (
            400,
            {"error": "Total amount is required"},
        )
        assert _json(client.post(path, json={"total_amount": 5}, headers=clerk_headers)) == (
            400,
            {"error": "Order items are required"},
        )
        assert _json(client.post(path, json={"total_amount": "x", "items": [{}]}, headers=clerk_headers)) == (
            400,
            {"error": "Total amount must be a number"},
        )
    path = "/api/storefront/soda/members/orders"
    assert _json(member_client.post(path, json={"items": [{}]})) == (400, {"error": "Total amount is required"})
    assert _json(member_client.post(path, json={"total_amount": 5})) == (400, {"error": "Order items are required"})
    item = {"product_id": 999999, "quantity": 1, "price": 1}
    assert _json(member_client.post(path, json={"total_amount": 1, "items": [item]})) == (
        404,
        {"error": "Product 999999 not found"},
    )


def test_clerk_email_mismatch(client, clerk_headers):
    for path in ("/api/storefront/soda/orders/other@asu.edu", "/api/storefront/soda/wallet/other@asu.edu"):
        assert _json(client.get(path, headers=clerk_headers)) == (403, {"error": "Unauthorized: Email mismatch"})
