"""Product and order queries for the storefront. No Flask here."""

from core import webhooks
from core.errors import ServiceError
from core.log import get_logger
from modules.auth import scopes
from modules.storefront.models import Order, Product

logger = get_logger(__name__)

webhooks.declare("order.created", "Store orders", "A member places an order in the store.", "storefront")
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
    catalog_total = sum(float(product.price) * quantity for product, quantity, _ in priced)
    return abs(catalog_total - float(total_amount)) > 0.005 or any(
        abs(float(product.price) - client_price) > 0.005 for product, _, client_price in priced
    )


def create_product(db, product, organization_id):
    """Add the product to the org and commit. Rolls back and raises on an error."""
    try:
        product.organization_id = organization_id
        db.add(product)
        db.commit()
        db.refresh(product)
        logger.info(f"Created storefront product '{product.name}' for organization {organization_id}")
        return product
    except Exception as e:
        logger.error(f"Error creating storefront product: {str(e)}")
        db.rollback()
        raise


def create_order(db, order, order_items, organization_id):
    """Add the order and its items to the org and commit. Rolls back and raises on an error."""
    try:
        order.organization_id = organization_id
        db.add(order)
        db.flush()

        for item in order_items:
            item.organization_id = organization_id
            item.order_id = order.id
            db.add(item)

        db.commit()
        db.refresh(order)
        logger.info(f"Created storefront order {order.id} for organization {organization_id}")
        _announce(order, len(order_items), organization_id)
        return order
    except Exception as e:
        logger.error(f"Error creating storefront order: {str(e)}")
        db.rollback()
        raise


def _announce(order, items: int, organization_id) -> None:
    """Send the order.created webhook event."""
    message = webhooks.Message(
        title=f"New store order #{order.id}",
        fields=(("Items", str(items)), ("Total", f"{float(order.total_amount or 0):g} points")),
        color=webhooks.GREEN,
    )
    webhooks.emit(int(organization_id), "order.created", message)


def products(db, organization_id):
    """The org's products, or [] on an error."""
    try:
        return db.query(Product).filter(Product.organization_id == organization_id).all()
    except Exception as e:
        logger.error(f"Error getting storefront products: {str(e)}")
        return []


def product(db, product_id, organization_id):
    """The org's product with this id, or None."""
    try:
        return db.query(Product).filter(Product.id == product_id, Product.organization_id == organization_id).first()
    except Exception as e:
        logger.error(f"Error getting storefront product: {str(e)}")
        return None


def orders(db, organization_id):
    """The org's orders, or [] on an error."""
    try:
        return db.query(Order).filter(Order.organization_id == organization_id).all()
    except Exception as e:
        logger.error(f"Error getting storefront orders: {str(e)}")
        return []


def order(db, order_id, organization_id):
    """The org's order with this id, or None."""
    try:
        return db.query(Order).filter(Order.id == order_id, Order.organization_id == organization_id).first()
    except Exception as e:
        logger.error(f"Error getting storefront order: {str(e)}")
        return None


def delete_product(db, product_id, organization_id) -> bool:
    """Delete the org's product and commit. False if it is missing or the delete fails."""
    try:
        found = product(db, product_id, organization_id)
        if found:
            db.delete(found)
            db.commit()
            logger.info(f"Deleted storefront product {product_id} for organization {organization_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting storefront product: {str(e)}")
        db.rollback()
        return False


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


def order_dict(order: Order) -> dict:
    """An order with its buyer and items, as the order list returns it."""
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


def change_order(order: Order, data: dict) -> None:
    """Set the status and message that data has. Raises StoreError for an unknown status. The caller commits."""
    if "status" in data:
        if data["status"] not in ORDER_STATUSES:
            raise StoreError(f"Invalid status. Must be one of: {', '.join(ORDER_STATUSES)}")
        order.status = data["status"]
    if "message" in data:
        order.message = data["message"]


def remove_order(db, order: Order, organization_id) -> None:
    """Delete an order. Its items go back in stock unless it is cancelled or delivered. The caller commits."""
    if order.status not in ["cancelled", "delivered"]:
        for item in order.items:
            found = product(db, item.product_id, organization_id)
            if found:
                found.stock += item.quantity
    db.delete(order)


def _all(db, model, ids: list[int], organization_id, label: str) -> list:
    rows = db.query(model).filter(model.id.in_(ids), model.organization_id == organization_id).all()
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
    """Delete products by id in one commit. If one id is missing, nothing changes."""
    rows = _all(db, Product, ids, organization_id, "products")
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": sorted(ids)}


def order_list(db, organization_id, status: str | None = None) -> list[dict]:
    """The org's orders, newest first. status keeps the orders with that status."""
    rows = [o for o in orders(db, organization_id) if status is None or o.status == status]
    return [order_dict(o) for o in sorted(rows, key=lambda o: o.id, reverse=True)]


def update_orders(db, organization_id, ids: list[int], data: dict) -> list[dict]:
    """Set the status or message of orders in one commit. If one id is missing, nothing changes."""
    rows = _all(db, Order, ids, organization_id, "orders")
    for row in rows:
        change_order(row, data)
    db.commit()
    return [order_dict(row) for row in rows]


def delete_orders(db, organization_id, ids: list[int]) -> dict:
    """Delete orders in one commit and put their items back in stock as remove_order does."""
    for row in _all(db, Order, ids, organization_id, "orders"):
        remove_order(db, row, organization_id)
    db.commit()
    return {"deleted": sorted(ids)}
