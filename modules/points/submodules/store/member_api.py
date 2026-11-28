"""Member routes of the store: the Discord member store and the Clerk wallet, orders and checkout.

The routes register on storefront_blueprint. modules/registry.py imports the blueprint from here, so they
register before the blueprint is mounted.
"""

from flask import g, request

from core.http.responses import error, error_handler
from modules.auth.decorators import dual_auth_required
from modules.auth.routes import member_view
from modules.members.service import get_or_create_user
from modules.points.submodules.store import service
from modules.points.submodules.store.api import in_org, place_order, refuse_price_change, storefront_blueprint

__all__ = ["storefront_blueprint"]

NO_USER = "Could not create or find user"


@storefront_blueprint.route("/<string:org_prefix>/members/store", methods=["GET"])
@error_handler
@member_view
def get_member_store(db, org, discord_id):
    """The store for a signed-in member of the org."""
    user = get_or_create_user(discord_id, org.id)
    user_info = {"discord_id": discord_id, "user_id": user.id if user else None, "is_member": True}
    front = service.store_front(db, org, timestamps=True)
    return {"organization": front["organization"], "user_info": user_info, "products": front["products"]}


@storefront_blueprint.route("/<string:org_prefix>/members/orders", methods=["GET"])
@error_handler
@member_view
def get_member_orders(db, org, discord_id):
    """The signed-in member's orders."""
    user = get_or_create_user(discord_id, org.id)
    if not user:
        return error(NO_USER, 500)
    return service.member_orders(db, org.id, user.id)


@storefront_blueprint.route("/<string:org_prefix>/members/orders", methods=["POST"])
@error_handler
@member_view
def create_member_order(db, org, discord_id):
    """Place a pending order for the signed-in member. It holds its points until a cancel or a delete."""
    user = get_or_create_user(discord_id, org.id)
    if not user:
        return error(NO_USER, 500)
    data = request.get_json()
    if not data.get("total_amount"):
        return error("Total amount is required", 400)
    if not data.get("items") or len(data["items"]) == 0:
        return error("Order items are required", 400)
    total_amount = service.parse_total(data["total_amount"])
    placed = service.checkout(
        db,
        org.id,
        user,
        total_amount,
        data["items"],
        refuse_price_change(org.prefix),
        status="pending",
        discord_user_id=discord_id,
    )
    return service.placed_json(placed, "Order created successfully", "points_held"), 201


@storefront_blueprint.route("/<string:org_prefix>/members/orders/<int:order_id>", methods=["GET"])
@error_handler
@member_view
def get_member_order(db, org, discord_id, order_id):
    """One order of the signed-in member."""
    return service.member_order(db, org.id, discord_id, order_id)


@storefront_blueprint.route("/<string:org_prefix>/members/points", methods=["GET"])
@error_handler
@member_view
def get_user_points_public(db, org, discord_id):
    """The signed-in member's points and newest entries."""
    return service.member_wallet(db, org.id, discord_id)


def _own_email(user_email):
    """The 403 response when the signed-in email is not user_email, else None."""
    if g.get("clerk_user_email") != user_email:
        return error("Unauthorized: Email mismatch", 403)
    return None


def _signed_in_user(user_email):
    """A view that returns the user with this email, made from the Clerk user when missing. Raises 500 or 404."""
    clerk_user = g.get("clerk_user")

    def find(db, org):
        user = service.clerk_buyer(db, org.id, user_email, clerk_user)
        if not user and clerk_user:
            raise service.StoreError("Failed to create user account", 500)
        if not user:
            raise service.StoreError("User not found", 404)
        return user

    return find


@storefront_blueprint.route("/<string:org_prefix>/orders/<string:user_email>", methods=["GET"])
@dual_auth_required
@error_handler
def get_user_orders_clerk(org_prefix, user_email):
    """The orders of the signed-in user, by email."""
    find = _signed_in_user(user_email)
    return _own_email(user_email) or in_org(
        org_prefix, lambda db, org: service.member_orders(db, org.id, find(db, org).id)
    )


@storefront_blueprint.route("/<string:org_prefix>/wallet/<string:user_email>", methods=["GET"])
@dual_auth_required
@error_handler
def get_user_wallet_clerk(org_prefix, user_email):
    """The points of the signed-in user, by email."""
    find = _signed_in_user(user_email)
    return _own_email(user_email) or in_org(org_prefix, lambda db, org: service.wallet(db, org.id, find(db, org)))


@storefront_blueprint.route("/<string:org_prefix>/checkout", methods=["POST"])
@dual_auth_required
@error_handler
def clerk_checkout(org_prefix):
    """Check out for the signed-in user. A Clerk user with no account gets one."""
    data = request.get_json()
    user_email = g.get("clerk_user_email")
    clerk_user = g.get("clerk_user")
    total_amount = service.order_totals(data)
    return place_order(
        org_prefix, total_amount, data["items"], lambda db, org: service.clerk_buyer(db, org.id, user_email, clerk_user)
    )
