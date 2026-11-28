"""Products, orders and checkout of the store, and the bodies its routes return. No Flask here."""

import math
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func

from core import webhooks
from core.errors import ServiceError
from core.log import get_logger
from modules.auth import scopes
from modules.members import service as members
from modules.members.models import User
from modules.points.models import Points
from modules.points.submodules.store.models import Order, OrderItem, Product

logger = get_logger(__name__)

webhooks.declare("order.created", "Store orders", "A member places an order in the store.", "points.store")
scopes.declare("store:read", "Read the store's products and orders, with the name and email of each buyer")
scopes.declare("store:write", "Add, change and delete products, and change the status of orders or delete them")

ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]
MAX_IDS = 100


class StoreError(ServiceError):
    pass


def normalize_category(value):
    """The category with whitespace stripped; an empty string becomes None."""
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    return value


def prices_mismatch(total_amount, priced) -> bool:
    """True if the client's total or a client unit price differs from the catalog by more than half a cent.

    priced holds (product, quantity, client unit price).
    """
    return abs(catalog_total(priced) - float(total_amount)) > 0.005 or any(
        abs(float(product.price) - client_price) > 0.005 for product, _, client_price in priced
    )


def parse_total(value) -> float:
    """The client's total as a positive number. Raises StoreError for a value that is not a positive number."""
    if isinstance(value, bool):
        raise StoreError("Total amount must be a number")
    try:
        total = float(value)
    except (TypeError, ValueError):
        raise StoreError("Total amount must be a number") from None
    if not math.isfinite(total) or total <= 0:
        raise StoreError("Total amount must be greater than 0")
    return total


def price_items(db, organization_id, items) -> tuple[list[OrderItem], list[tuple[Product, int, float]]]:
    """Order items at catalog prices, and the (product, quantity, client unit price) of each. Changes no stock.

    Raises StoreError for a bad item, a product that is not in the org, or too little stock.
    """
    if not isinstance(items, list) or not items:
        raise StoreError("Order items are required")
    order_items: list[OrderItem] = []
    priced: list[tuple[Product, int, float]] = []
    wanted: Counter[int] = Counter()
    for item in items:
        if not isinstance(item, dict) or not all(k in item for k in ("product_id", "quantity", "price")):
            raise StoreError("Each item must have product_id, quantity, and price")
        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
            client_price = float(item["price"])
        except (TypeError, ValueError):
            raise StoreError("Each item must have a numeric product_id, quantity, and price") from None
        if quantity < 1:
            raise StoreError("Quantity must be at least 1")
        found = product(db, product_id, organization_id, for_update=True)
        if not found:
            raise StoreError(f"Product {product_id} not found", 404)
        wanted[found.id] += quantity
        if found.stock < wanted[found.id]:
            raise StoreError(f"Insufficient stock for product {found.name}")
        priced.append((found, quantity, client_price))
        order_items.append(OrderItem(product_id=found.id, quantity=quantity, price_at_time=float(found.price)))
    return order_items, priced


def catalog_total(priced) -> float:
    """The sum of catalog price times quantity. priced holds (product, quantity, client unit price)."""
    return float(sum(float(product.price) * quantity for product, quantity, _ in priced))


def take_stock(priced) -> None:
    """Lower the stock of each product by its quantity. The caller commits."""
    for found, quantity, _ in priced:
        found.stock -= quantity


def points_number(value: float) -> float | int:
    """The value as an int when it has no fraction, else the float."""
    return int(value) if float(value).is_integer() else value


def purchase_event(order_id) -> str:
    """The event of the points entry that pays for an order."""
    return f"Storefront Purchase - Order #{order_id}"


def refund_event(order_id) -> str:
    """The event of the points entry that gives back the points of an order."""
    return f"Refund - Order #{order_id}"


def locked_balance(db, user_id, organization_id):
    """The user's points in the org, read after a lock on the user's row that holds until the commit.

    Two checkouts of one member thus run one after the other, so both cannot spend the same points.
    """
    db.query(User.id).filter(User.id == user_id).with_for_update().one()
    return (
        db.query(func.sum(Points.points))
        .filter(Points.user_id == user_id, Points.organization_id == organization_id)
        .scalar()
        or 0
    )


def place_order(db, organization_id, user: User, order_items, priced, *, status: str, discord_user_id=None) -> Order:
    """Write the order, the stock change and the points it holds in one commit, at the catalog total.

    The hold is the negative purchase entry; a cancel or a delete gives it back. Raises StoreError 400 with
    nothing written when the member has fewer points than the total.
    """
    charge = catalog_total(priced)
    balance = locked_balance(db, user.id, organization_id)
    if balance < charge:
        db.rollback()
        logger.info(
            "order refused org_id=%s user_id=%s balance=%s charge=%s", organization_id, user.id, balance, charge
        )
        raise StoreError(f"Insufficient points. You have {balance} points but need {points_number(charge)}")
    take_stock(priced)
    order = Order(user_id=user.id, discord_user_id=discord_user_id, total_amount=charge, status=status)
    return create_order(db, order, order_items, organization_id, charge=charge)


def held_points(db, organization_id, order_ids) -> dict[int, float]:
    """The points each order holds: its purchase entry less its refunds. An order with no purchase entry holds 0."""
    ids = list(order_ids)
    if not ids:
        return {}
    events = {purchase_event(i): i for i in ids} | {refund_event(i): i for i in ids}
    rows = (
        db.query(Points.event, func.sum(Points.points))
        .filter(Points.organization_id == organization_id, Points.event.in_(list(events)))
        .group_by(Points.event)
        .all()
    )
    held = dict.fromkeys(ids, 0.0)
    for event, total in rows:
        held[events[event]] -= float(total or 0)
    return {order_id: points_number(max(value, 0.0)) for order_id, value in held.items()}


def create_product(db, product, organization_id):
    """Add the product to the org and commit. Rolls back and raises on an error."""
    try:
        product.organization_id = organization_id
        db.add(product)
        db.commit()
        db.refresh(product)
    except Exception:
        logger.exception("product create failed org_id=%s name=%r", organization_id, product.name)
        db.rollback()
        raise
    logger.info("product created org_id=%s product_id=%s name=%r", organization_id, product.id, product.name)
    return product


def create_order(db, order, order_items, organization_id, charge: float | None = None):
    """Add the order and its items to the org and commit. Rolls back and raises on an error.

    With charge, a negative points entry of that amount pays for the order in the same commit.
    """
    try:
        order.organization_id = organization_id
        db.add(order)
        db.flush()

        for item in order_items:
            item.organization_id = organization_id
            item.order_id = order.id
            db.add(item)

        if charge is not None:
            db.add(
                Points(
                    user_id=order.user_id,
                    organization_id=organization_id,
                    points=-charge,
                    event=purchase_event(order.id),
                    timestamp=datetime.now(UTC),
                    awarded_by_officer="System",
                )
            )

        db.commit()
        db.refresh(order)
    except Exception:
        logger.exception("order create failed org_id=%s user_id=%s", organization_id, order.user_id)
        db.rollback()
        raise
    logger.info(
        "order created org_id=%s order_id=%s user_id=%s status=%s charge=%s",
        organization_id,
        order.id,
        order.user_id,
        order.status,
        charge,
    )
    _announce(order, len(order_items), organization_id)
    return order


def _announce(order, items: int, organization_id) -> None:
    """Send the order.created webhook event."""
    message = webhooks.Message(
        title=f"New store order #{order.id}",
        fields=(("Items", str(items)), ("Total", f"{float(order.total_amount or 0):g} points")),
        color=webhooks.GREEN,
    )
    webhooks.emit(int(organization_id), "order.created", message)


def products(db, organization_id):
    """The org's products."""
    return db.query(Product).filter(Product.organization_id == organization_id).all()


def product(db, product_id, organization_id, for_update=False):
    """The org's product with this id, or None. for_update locks the row until the caller commits."""
    query = db.query(Product).filter(Product.id == product_id, Product.organization_id == organization_id)
    return (query.with_for_update() if for_update else query).first()


def orders(db, organization_id):
    """The org's orders."""
    return db.query(Order).filter(Order.organization_id == organization_id).all()


def order(db, order_id, organization_id, for_update: bool = False):
    """The org's order with this id, or None. With for_update, the row stays locked until the commit."""
    query = db.query(Order).filter(Order.id == order_id, Order.organization_id == organization_id)
    return (query.with_for_update() if for_update else query).first()


def _check_no_orders(db, product_ids) -> None:
    """Raises StoreError 409 if an order item refers to one of the products."""
    if db.query(OrderItem.id).filter(OrderItem.product_id.in_(product_ids)).first():
        raise StoreError("Product has orders. Set its stock to 0 to hide it from the store.", 409)


def delete_product(db, product_id, organization_id) -> bool:
    """Delete the org's product and commit. False if it is missing.

    Raises StoreError 409 if an order has the product.
    """
    found = product(db, product_id, organization_id)
    if not found:
        return False
    _check_no_orders(db, [found.id])
    db.delete(found)
    db.commit()
    logger.info("product deleted org_id=%s product_id=%s", organization_id, product_id)
    return True


def product_dict(product: Product) -> dict:
    """A product as the officer routes and tools return it."""
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "image_url": product.image_url,
        "category": product.category,
        "organization_id": product.organization_id,
    }


def order_dict(order: Order, points_held: float = 0) -> dict:
    """An order with its buyer, items and the points it holds, as the order list returns it."""
    return {
        "id": order.id,
        "user_id": order.user_id,
        "total_amount": order.total_amount,
        "status": order.status,
        "message": order.message,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "organization_id": order.organization_id,
        "user_name": order.user.name if order.user else "Unknown User",
        "user_email": order.user.email if order.user else None,
        "items": [
            {"id": i.id, "product_id": i.product_id, "quantity": i.quantity, "price_at_time": i.price_at_time}
            for i in order.items
        ],
        "points_held": points_held,
    }


def change_product(product: Product, data: dict) -> None:
    """Set the product fields that data has. The caller commits."""
    if "name" in data:
        product.name = data["name"]
    if "description" in data:
        product.description = data["description"]
    if "price" in data:
        product.price = float(data["price"])
    if "stock" in data:
        product.stock = int(data["stock"])
    if "image_url" in data:
        product.image_url = data["image_url"]
    if "category" in data:
        product.category = normalize_category(data["category"])


def _restock(db, order: Order, organization_id) -> None:
    """Put the items of the order back in stock. The caller commits."""
    for item in order.items:
        found = product(db, item.product_id, organization_id, for_update=True)
        if found:
            found.stock += item.quantity


def _refund(db, order: Order, organization_id) -> None:
    """Add a points entry that gives back what the order took, less refunds already given. The caller commits.

    An order with no purchase entry, such as a pending member order, gets no refund.
    """
    rows = (
        db.query(Points.points)
        .filter(
            Points.organization_id == organization_id,
            Points.user_id == order.user_id,
            Points.event.in_([purchase_event(order.id), refund_event(order.id)]),
        )
        .all()
    )
    owed = -sum(float(row.points or 0) for row in rows)
    if owed > 0:
        db.add(
            Points(
                user_id=order.user_id,
                organization_id=organization_id,
                points=owed,
                event=refund_event(order.id),
                timestamp=datetime.now(UTC),
                awarded_by_officer="System",
            )
        )


def change_order(db, order: Order, data: dict) -> None:
    """Set the status and message that data has. The caller commits.

    A change to cancelled puts the items back in stock and refunds the points. Raises StoreError for an unknown
    status, and 409 for a change away from cancelled.
    """
    if "status" in data:
        status = data["status"]
        if status not in ORDER_STATUSES:
            raise StoreError(f"Invalid status. Must be one of: {', '.join(ORDER_STATUSES)}")
        if order.status == "cancelled" and status != "cancelled":
            raise StoreError("A cancelled order cannot change status. Place a new order.", 409)
        if status == "cancelled" and order.status != "cancelled":
            _restock(db, order, order.organization_id)
            _refund(db, order, order.organization_id)
        order.status = status
    if "message" in data:
        order.message = data["message"]


def remove_order(db, order: Order, organization_id) -> None:
    """Delete an order. The caller commits.

    Unless the order is cancelled or delivered, its items go back in stock and its points are refunded.
    """
    if order.status not in ["cancelled", "delivered"]:
        _restock(db, order, organization_id)
        _refund(db, order, organization_id)
    db.delete(order)


def _all(db, model, ids: list[int], organization_id, label: str, for_update: bool = False) -> list:
    query = db.query(model).filter(model.id.in_(ids), model.organization_id == organization_id)
    rows = (query.with_for_update() if for_update else query).all()
    missing = sorted(set(ids) - {row.id for row in rows})
    if missing:
        raise StoreError(f"No {label} with ids {', '.join(str(i) for i in missing)}", 404)
    return rows


def save_product(db, organization_id, data: dict, product_id: int | None = None) -> dict:
    """Add a product, or change the product with product_id. Commits."""
    if product_id is None:
        for key in ("name", "price", "stock"):
            if data.get(key) in (None, ""):
                raise StoreError(f"Product {key} is required")
        row = Product(
            name=data["name"],
            description=data.get("description", ""),
            price=float(data["price"]),
            stock=int(data["stock"]),
            image_url=data.get("image_url", ""),
            category=normalize_category(data.get("category")),
        )
        return product_dict(create_product(db, row, organization_id))
    found = product(db, product_id, organization_id)
    if found is None:
        raise StoreError("Product not found", 404)
    change_product(found, data)
    db.commit()
    return product_dict(found)


def delete_products(db, organization_id, ids: list[int]) -> dict:
    """Delete products by id in one commit. If one id is missing or has orders, nothing changes."""
    rows = _all(db, Product, ids, organization_id, "products")
    _check_no_orders(db, [row.id for row in rows])
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": sorted(ids)}


def order_list(db, organization_id, status: str | None = None) -> list[dict]:
    """The org's orders, newest first. status keeps the orders with that status."""
    rows = [o for o in orders(db, organization_id) if status is None or o.status == status]
    held = held_points(db, organization_id, [o.id for o in rows])
    return [order_dict(o, held[o.id]) for o in sorted(rows, key=lambda o: o.id, reverse=True)]


def update_orders(db, organization_id, ids: list[int], data: dict) -> list[dict]:
    """Set the status or message of orders in one commit. If one id is missing, nothing changes."""
    rows = _all(db, Order, ids, organization_id, "orders", for_update=True)
    for row in rows:
        change_order(db, row, data)
    db.commit()
    held = held_points(db, organization_id, [row.id for row in rows])
    return [order_dict(row, held[row.id]) for row in rows]


def delete_orders(db, organization_id, ids: list[int]) -> dict:
    """Delete orders in one commit. Stock and points go back as remove_order does."""
    for row in _all(db, Order, ids, organization_id, "orders", for_update=True):
        remove_order(db, row, organization_id)
    db.commit()
    return {"deleted": sorted(ids)}


# Bodies of the store routes

PRICES_CHANGED = "Prices have changed. Reload the store and try again."


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def catalog_json(found: Product) -> dict:
    """A product with its timestamps, as the product list and the product route return it."""
    return {**product_dict(found), "created_at": _iso(found.created_at), "updated_at": _iso(found.updated_at)}


def product_list(db, organization_id) -> list[dict]:
    """Every product of the org."""
    return [catalog_json(p) for p in products(db, organization_id)]


def product_detail(db, product_id, organization_id) -> dict:
    """One product of the org. Raises StoreError 404 when it is missing."""
    found = product(db, product_id, organization_id)
    if not found:
        raise StoreError("Product not found", 404)
    return catalog_json(found)


def new_product(data: dict) -> Product:
    """A product from the officer's form, not yet added. Raises StoreError when name, price or stock is empty."""
    for key in ("name", "price", "stock"):
        if not data.get(key):
            raise StoreError(f"Product {key} is required")
    return Product(
        name=data["name"],
        description=data.get("description", ""),
        price=float(data["price"]),
        stock=int(data["stock"]),
        image_url=data.get("image_url", ""),
        category=normalize_category(data.get("category")),
    )


def add_product(db, organization_id, row: Product) -> dict:
    """Add the product to the org. Commits."""
    created = create_product(db, row, organization_id)
    return {"message": "Product created successfully", "id": created.id, "product": product_dict(created)}


def update_product(db, organization_id, product_id, data: dict) -> dict:
    """Set the product fields that data has. Commits. Raises StoreError 404 when the product is missing."""
    found = product(db, product_id, organization_id)
    if not found:
        raise StoreError("Product not found", 404)
    change_product(found, data)
    db.commit()
    return {"message": "Product updated successfully", "product": product_dict(found)}


def remove_product(db, organization_id, product_id) -> dict:
    """Delete the product. Commits. Raises StoreError 404 when it is missing and 409 when an order has it."""
    if not delete_product(db, product_id, organization_id):
        raise StoreError("Product not found", 404)
    return {"message": "Product deleted successfully"}


def order_detail(db, order_id, organization_id) -> dict:
    """One order of the org with its items. Raises StoreError 404 when it is missing."""
    found = order(db, order_id, organization_id)
    if not found:
        raise StoreError("Order not found", 404)
    return {
        "id": found.id,
        "user_id": found.user_id,
        "total_amount": found.total_amount,
        "status": found.status,
        "created_at": found.created_at.isoformat(),
        "updated_at": _iso(found.updated_at),
        "organization_id": found.organization_id,
        "items": [
            {"id": i.id, "product_id": i.product_id, "quantity": i.quantity, "price_at_time": i.price_at_time}
            for i in found.items
        ],
    }


def update_order(db, organization_id, order_id, data: dict) -> dict:
    """Set the status and message of the order, with the row locked. Commits.

    Raises StoreError 404 when the order is missing, and the errors of change_order.
    """
    found = order(db, order_id, organization_id, for_update=True)
    if not found:
        raise StoreError("Order not found", 404)
    change_order(db, found, data)
    db.commit()
    return {
        "message": "Order updated successfully",
        "order": {
            "id": found.id,
            "user_id": found.user_id,
            "total_amount": found.total_amount,
            "status": found.status,
            "message": found.message,
            "updated_at": _iso(found.updated_at),
        },
    }


def delete_order(db, organization_id, order_id) -> dict:
    """Delete the order, with the row locked, as remove_order does. Commits. Raises StoreError 404 when missing."""
    found = order(db, order_id, organization_id, for_update=True)
    if not found:
        raise StoreError("Order not found", 404)
    remove_order(db, found, organization_id)
    db.commit()
    return {"message": "Order deleted successfully"}


def _store_product(found: Product, timestamps: bool) -> dict:
    row = {
        "id": found.id,
        "name": found.name,
        "description": found.description,
        "price": found.price,
        "stock": found.stock,
        "image_url": found.image_url,
    }
    if timestamps:
        row |= {"created_at": _iso(found.created_at), "updated_at": _iso(found.updated_at)}
    return row


def store_front(db, org, timestamps: bool = False) -> dict:
    """The org and its products in stock. timestamps adds created_at and updated_at to each product."""
    return {
        "organization": {"name": org.name, "prefix": org.prefix, "description": org.description},
        "products": [_store_product(p, timestamps) for p in products(db, org.id) if p.stock > 0],
    }


def order_totals(data: dict) -> float:
    """The client's total of an order body. Raises StoreError when the total or the items are missing or bad."""
    if not data.get("total_amount"):
        raise StoreError("Total amount is required")
    if not data.get("items") or len(data["items"]) == 0:
        raise StoreError("Order items are required")
    return parse_total(data["total_amount"])


def active_buyer(db, organization_id, user: User | None) -> User:
    """The user, who must be an active member of the org. Raises StoreError 404 or 403."""
    if not user:
        raise StoreError("User not found", 404)
    if not members.active_membership(db, user.id, organization_id):
        raise StoreError("User is not a member of this organization", 403)
    return user


def checkout(
    db,
    organization_id,
    user: User,
    total_amount: float,
    items,
    refuse_price_change: Callable[[], bool],
    *,
    status: str,
    discord_user_id=None,
) -> Order:
    """Price the items from the catalog, then write the order, the stock change and the points in one commit.

    The charge is the catalog total, not the client's total. When the client's prices differ from the catalog,
    refuse_price_change() says whether to refuse the order with StoreError 409.
    """
    order_items, priced = price_items(db, organization_id, items)
    if prices_mismatch(total_amount, priced) and refuse_price_change():
        raise StoreError(PRICES_CHANGED, 409)
    return place_order(db, organization_id, user, order_items, priced, status=status, discord_user_id=discord_user_id)


def placed_json(placed: Order, message: str, points_key: str) -> dict:
    """The body of a placed order. points_key names the points it took or holds."""
    return {
        "message": message,
        "id": placed.id,
        points_key: points_number(placed.total_amount),
        "order": {
            "id": placed.id,
            "user_id": placed.user_id,
            "total_amount": placed.total_amount,
            "status": placed.status,
            "created_at": _iso(placed.created_at),
        },
    }


def _member_items(found: Order) -> list[dict]:
    return [
        {
            "id": item.id,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "price_at_time": item.price_at_time,
            "product_name": item.product.name if item.product else "Unknown Product",
        }
        for item in found.items
    ]


def member_orders(db, organization_id, user_id) -> list[dict]:
    """The member's orders in the org, newest first, with the items and the points each order holds."""
    rows = (
        db.query(Order)
        .filter(Order.organization_id == organization_id, Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .all()
    )
    held = held_points(db, organization_id, [o.id for o in rows])
    return [
        {
            "id": o.id,
            "total_amount": o.total_amount,
            "status": o.status,
            "message": o.message,
            "created_at": o.created_at.isoformat(),
            "updated_at": _iso(o.updated_at),
            "items": _member_items(o),
            "points_held": held[o.id],
        }
        for o in rows
    ]


def member_order(db, organization_id, discord_id, order_id) -> dict:
    """One order of the member with this Discord id. Raises StoreError 404 when either is missing."""
    user = db.query(User).filter_by(discord_id=discord_id).first() if discord_id else None
    found = (
        db.query(Order)
        .filter(Order.id == order_id, Order.organization_id == organization_id, Order.user_id == user.id)
        .first()
        if user
        else None
    )
    if not found:
        raise StoreError("Order not found", 404)
    return {
        "id": found.id,
        "total_amount": found.total_amount,
        "status": found.status,
        "created_at": found.created_at.isoformat(),
        "updated_at": _iso(found.updated_at),
        "items": _member_items(found),
    }


def wallet(db, organization_id, user: User) -> dict:
    """The user's points in the org and the newest 20 entries."""
    total = (
        db.query(func.sum(Points.points))
        .filter(Points.user_id == user.id, Points.organization_id == organization_id)
        .scalar()
        or 0
    )
    rows = (
        db.query(Points)
        .filter_by(user_id=user.id, organization_id=organization_id)
        .order_by(Points.timestamp.desc())
        .limit(20)
        .all()
    )
    return {
        "email": user.email,
        "total_points": total,
        "points_breakdown": [
            {"points": p.points, "event": p.event, "timestamp": _iso(p.timestamp), "awarded_by": p.awarded_by_officer}
            for p in rows
        ],
    }


def member_wallet(db, organization_id, discord_id) -> dict:
    """The wallet of the active member with this Discord id. Raises StoreError 404 or 403."""
    user = db.query(User).filter_by(discord_id=discord_id).first() if discord_id else None
    return wallet(db, organization_id, active_buyer(db, organization_id, user))


def clerk_buyer(db, organization_id, email: str | None, clerk_user) -> User | None:
    """The user with this email. With a Clerk user, a missing user is created as a member of the org."""
    user = db.query(User).filter(User.email == email).first()
    if not user and clerk_user:
        user = members.get_or_create_user_from_clerk(db, organization_id, clerk_user, email)
    return user
