import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up logger
logger = logging.getLogger(__name__)

# Create a centralized Base for all models
from .base import Base


class DBConnect:
    def __init__(self, db_url="sqlite:///./data/user.db") -> None:
        self.SQLALCHEMY_DATABASE_URL = db_url

        # Ensure the database directory exists
        self._ensure_db_directory()

        self.engine = create_engine(
            self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.check_and_create_tables()

    def _ensure_db_directory(self):
        """Extract the database file path and ensure its directory exists"""
        if self.SQLALCHEMY_DATABASE_URL.startswith('sqlite:///'):
            # Remove sqlite:/// prefix to get the file path
            db_path = self.SQLALCHEMY_DATABASE_URL[10:]

            # Normalize path to handle potential ./ prefix
            db_path = os.path.normpath(db_path)

            # Get the directory part of the path
            db_dir = os.path.dirname(db_path)

            # If there's a directory component and it doesn't exist, create it
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"Created database directory: {db_dir}")

    def check_and_create_tables(self):
        """Create all tables if they don't exist"""
        print("Creating database tables...")
        Base.metadata.create_all(bind=self.engine)
        print("Database tables created successfully")
        """Check if database file exists and create tables if needed"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.SQLALCHEMY_DATABASE_URL.replace('sqlite:///', '')), exist_ok=True)

            # Check if the database file exists
            db_path = self.SQLALCHEMY_DATABASE_URL.replace('sqlite:///', '')
            if not os.path.exists(db_path):
                logger.info(f"Database file does not exist at {db_path}. Creating tables...")
                # Import all models to register them with Base

                Base.metadata.create_all(bind=self.engine)
                logger.info("Database tables created successfully")
            else:
                logger.info(f"Database file already exists at {db_path}. Using existing database.")
        except Exception as e:
            logger.error(f"Error checking/creating database tables: {str(e)}")
            raise

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create_user(self, db, user):
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def create_point(self, db, point):
        db.add(point)
        db.commit()
        db.refresh(point)
        return point

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
            return db.query(Product).filter(
                Product.id == product_id,
                Product.organization_id == organization_id
            ).first()
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
            return db.query(Order).filter(
                Order.id == order_id,
                Order.organization_id == organization_id
            ).first()
        except Exception as e:
            logger.error(f"Error getting storefront order: {str(e)}")
            return None

    def update_storefront_product_stock(self, db, product_id, organization_id, new_stock):
        """Update storefront product stock for a specific organization"""
        try:
            product = self.get_storefront_product(db, product_id, organization_id)
            if product:
                product.stock = new_stock
                db.commit()
                logger.info(f"Updated stock for storefront product {product_id} to {new_stock}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating storefront product stock: {str(e)}")
            db.rollback()
            return False

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
