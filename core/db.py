import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import config
from core.logging_config import get_logger

logger = get_logger(__name__)


class DBConnect:
    def __init__(self, db_url="sqlite:///./data/user.db") -> None:
        self.SQLALCHEMY_DATABASE_URL = db_url

        # Ensure the database directory exists
        self._ensure_db_directory()

        # The schema comes from Alembic migrations (alembic upgrade head), not create_all at startup
        if self.SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
            self.engine = create_engine(self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
        else:
            self.engine = create_engine(self.SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _ensure_db_directory(self):
        """Extract the database file path and ensure its directory exists"""
        if self.SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
            # Remove sqlite:/// prefix to get the file path
            db_path = self.SQLALCHEMY_DATABASE_URL[10:]

            # Normalize path to handle potential ./ prefix
            db_path = os.path.normpath(db_path)

            # Get the directory part of the path
            db_dir = os.path.dirname(db_path)

            # If there's a directory component and it doesn't exist, create it
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Storefront-related methods
    def create_storefront_product(self, db, product, organization_id):
        """Create a new storefront product for a specific organization"""
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

    def create_storefront_order(self, db, order, order_items, organization_id):
        """Create a new storefront order with items for a specific organization"""
        try:
            order.organization_id = organization_id
            db.add(order)
            db.flush()  # Flush to get the order ID

            for item in order_items:
                item.organization_id = organization_id
                item.order_id = order.id
                db.add(item)

            db.commit()
            db.refresh(order)
            logger.info(f"Created storefront order {order.id} for organization {organization_id}")
            return order
        except Exception as e:
            logger.error(f"Error creating storefront order: {str(e)}")
            db.rollback()
            raise

    def get_storefront_products(self, db, organization_id):
        """Get all storefront products for a specific organization"""
        try:
            from modules.storefront.models import Product

            return db.query(Product).filter(Product.organization_id == organization_id).all()
        except Exception as e:
            logger.error(f"Error getting storefront products: {str(e)}")
            return []

    def get_storefront_product(self, db, product_id, organization_id):
        """Get a storefront product by ID for a specific organization"""
        try:
            from modules.storefront.models import Product

            return (
                db.query(Product).filter(Product.id == product_id, Product.organization_id == organization_id).first()
            )
        except Exception as e:
            logger.error(f"Error getting storefront product: {str(e)}")
            return None

    def get_storefront_orders(self, db, organization_id):
        """Get all storefront orders for a specific organization"""
        try:
            from modules.storefront.models import Order

            return db.query(Order).filter(Order.organization_id == organization_id).all()
        except Exception as e:
            logger.error(f"Error getting storefront orders: {str(e)}")
            return []

    def get_storefront_order(self, db, order_id, organization_id):
        """Get a storefront order by ID for a specific organization"""
        try:
            from modules.storefront.models import Order

            return db.query(Order).filter(Order.id == order_id, Order.organization_id == organization_id).first()
        except Exception as e:
            logger.error(f"Error getting storefront order: {str(e)}")
            return None

    def delete_storefront_product(self, db, product_id, organization_id):
        """Delete a storefront product for a specific organization"""
        try:
            product = self.get_storefront_product(db, product_id, organization_id)
            if product:
                db.delete(product)
                db.commit()
                logger.info(f"Deleted storefront product {product_id} for organization {organization_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting storefront product: {str(e)}")
            db.rollback()
            return False


db_connect = DBConnect(config.DATABASE_URL)


@contextmanager
def session() -> Iterator[Session]:
    """A database session that commits on success, rolls back on an error and always closes."""
    db = db_connect.SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
