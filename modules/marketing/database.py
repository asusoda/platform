"""
Database operations for marketing events
"""
from modules.utils.db import DBConnect
from modules.marketing.models import MarketingEvent
from shared import logger


def get_all_event_ids():
    """
    Get all event IDs from the database
    
    Returns:
        set: Set of event IDs that exist in the database
    """
    try:
        with DBConnect() as db:
            event_ids = db.session.query(MarketingEvent.event_id).all()
            return {event_id[0] for event_id in event_ids}
    except Exception as e:
        logger.error(f"Error getting all event IDs: {str(e)}")
        return set()


def get_all_completed_events():
    """
    Get all completed event IDs from the database
    
    Returns:
        set: Set of event IDs that are marked as completed
    """
    try:
        with DBConnect() as db:
            completed_events = db.session.query(MarketingEvent.event_id).filter(
                MarketingEvent.is_completed == True
            ).all()
            return {event_id[0] for event_id in completed_events}
    except Exception as e:
        logger.error(f"Error getting completed events: {str(e)}")
        return set()