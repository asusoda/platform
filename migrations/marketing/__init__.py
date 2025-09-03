import os
from modules.utils.db import DBConnect
from modules.marketing.models import MarketingEvent, MarketingConfig, MarketingLog
import logging

logger = logging.getLogger(__name__)

def run_migration():
    """Create the marketing tables if they don't exist"""
    try:
        # Initialize database connection using the shared DBConnect
        db_connect = DBConnect("sqlite:///./data/user.db")
        
        # Create tables using SQLAlchemy
        from modules.points.models import Base
        Base.metadata.create_all(bind=db_connect.engine)
        
        logger.info("Marketing module migration completed successfully")
        
        # Set up default configuration values
        db = next(db_connect.get_db())
        try:
            # Check if default configs exist, if not create them
            default_configs = [
                {
                    'key': 'monitoring_active',
                    'value': 'false',
                    'description': 'Whether automatic event monitoring is active'
                },
                {
                    'key': 'check_interval',
                    'value': '3600',
                    'description': 'Interval in seconds for checking new events'
                },
                {
                    'key': 'notification_enabled',
                    'value': 'true',
                    'description': 'Whether to send Discord notifications for new events'
                },
                {
                    'key': 'auto_generate_content',
                    'value': 'true',
                    'description': 'Whether to automatically generate content for new events'
                }
            ]
            
            for config_data in default_configs:
                existing = db.query(MarketingConfig).filter(
                    MarketingConfig.key == config_data['key']
                ).first()
                
                if not existing:
                    config_item = MarketingConfig(**config_data)
                    db.add(config_item)
            
            db.commit()
            logger.info("Default marketing configurations created")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating default configurations: {e}")
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in marketing migration: {e}")
        raise
