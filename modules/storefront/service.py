"""Product and order queries for the storefront. No Flask here."""

from core import webhooks
from core.log import get_logger
from modules.storefront.models import Order, Product

logger = get_logger(__name__)

webhooks.declare("order.created", "Store orders", "A member places an order in the store.", "storefront")


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
