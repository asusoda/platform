"""Officer and public routes of the store. The logic and the bodies are in service.py.

The officer routes accept an inactive org too, so they do not use officer_route.
"""

from flask import Blueprint, g, request

from core.db import db_connect
from core.http.responses import error, error_handler
from modules.auth.access import decide
from modules.auth.decorators import auth_required, dual_auth_required, org_officer_required
from modules.auth.routes import respond
from modules.organizations.service import find_by_prefix
from modules.points.submodules.store import service

storefront_blueprint = Blueprint("storefront", __name__)


def in_org(org_prefix, view, *args):
    """Run view(db, org, *args) for the org with this prefix, active or not, and make the result a response.

    No org gets 404. A StoreError becomes its message and status.
    """
    db = db_connect.SessionLocal()
    try:
        org = find_by_prefix(db, org_prefix)
        if not org:
            return error("Organization not found", 404)
        return respond(db, view, org, *args)
    finally:
        db.close()


def refuse_price_change(org_prefix):
    """Whether a checkout whose client prices differ from the catalog is refused.

    The mismatch is logged as checkout_price_mismatch, and refused only when ACCESS_ENFORCE is true.
    """
    return lambda: decide("checkout_price_mismatch", org=org_prefix)


def place_order(org_prefix, total_amount: float, items, user_for):
    """Check out for the user that user_for(db, org) returns, as an active member of the org. 201 with the order."""

    def view(db, org):
        user = service.active_buyer(db, org.id, user_for(db, org))
        placed = service.checkout(
            db, org.id, user, total_amount, items, refuse_price_change(org_prefix), status="completed"
        )
        return service.placed_json(placed, "Order placed and points deducted successfully", "points_deducted"), 201

    return in_org(org_prefix, view)


@storefront_blueprint.route("/<string:org_prefix>/products", methods=["GET"])
@error_handler
def get_products(org_prefix):
    """Every product of the org."""
    return in_org(org_prefix, lambda db, org: service.product_list(db, org.id))


@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["GET"])
@error_handler
def get_product(org_prefix, product_id):
    """One product of the org."""
    return in_org(org_prefix, lambda db, org: service.product_detail(db, product_id, org.id))


@storefront_blueprint.route("/<string:org_prefix>/products", methods=["POST"])
@auth_required
@error_handler
def create_product(org_prefix):
    """Add a product to the org. 201 with the product."""
    row = service.new_product(request.get_json())
    return in_org(org_prefix, lambda db, org: (service.add_product(db, org.id, row), 201))


@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["PUT"])
@auth_required
@error_handler
def update_product(org_prefix, product_id):
    """Change the product fields that the body has."""
    return in_org(org_prefix, lambda db, org: service.update_product(db, org.id, product_id, request.get_json()))


@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_product(org_prefix, product_id):
    """Delete a product that no order has."""
    return in_org(org_prefix, lambda db, org: service.remove_product(db, org.id, product_id))


@storefront_blueprint.route("/<string:org_prefix>/orders", methods=["GET"])
@dual_auth_required
@org_officer_required
@error_handler
def get_orders(org_prefix):
    """Every order of the org, with its buyer and the points it holds."""

    def view(db, org):
        orders = service.orders(db, org.id)
        held = service.held_points(db, org.id, [o.id for o in orders])
        return [service.order_dict(o, held[o.id]) for o in orders]

    return in_org(org_prefix, view)


@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["GET"])
@auth_required
@error_handler
def get_order(org_prefix, order_id):
    """One order of the org with its items."""
    return in_org(org_prefix, lambda db, org: service.order_detail(db, order_id, org.id))


@storefront_blueprint.route("/<string:org_prefix>/orders", methods=["POST"])
@dual_auth_required
@error_handler
def create_order(org_prefix):
    """Check out for the signed-in user, found by the email of the Clerk or platform token."""
    data = request.get_json()
    user_email = g.get("clerk_user_email")
    if not user_email or "@" not in user_email:
        return error("Authenticated user email is missing or invalid", 400)
    total_amount = service.order_totals(data)
    return place_order(
        org_prefix, total_amount, data["items"], lambda db, org: service.clerk_buyer(db, org.id, user_email, None)
    )


@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["PUT"])
@auth_required
@error_handler
def update_order_status(org_prefix, order_id):
    """Change the status or message of an order. A cancel gives back the stock and the points."""
    return in_org(org_prefix, lambda db, org: service.update_order(db, org.id, order_id, request.get_json()))


@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_order(org_prefix, order_id):
    """Delete an order. Unless it is cancelled or delivered, the stock and the points go back."""
    return in_org(org_prefix, lambda db, org: service.delete_order(db, org.id, order_id))


@storefront_blueprint.route("/<string:org_prefix>/store", methods=["GET"])
@error_handler
def get_store_products(org_prefix):
    """The public store: the org and its products in stock."""
    return in_org(org_prefix, lambda db, org: service.store_front(db, org))


@storefront_blueprint.route("/<string:org_prefix>/store/purchase", methods=["POST"])
@auth_required
@error_handler
def purchase_products(org_prefix):
    """The same checkout as create_order."""
    return create_order(org_prefix)
