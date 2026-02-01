"""
Pytest configuration and fixtures for testing.
"""
import pytest
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def app():
    """Create and configure a test Flask application instance."""
    # Set testing environment
    os.environ['TESTING'] = 'true'
    
    # Import after setting env var
    from main import app as flask_app
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
    })
    
    yield flask_app


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    mock_session = MagicMock()
    return mock_session


@pytest.fixture
def mock_organization():
    """Create a mock organization object."""
    org = MagicMock()
    org.id = 1
    org.prefix = "test-org"
    org.name = "Test Organization"
    org.is_active = True
    return org


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = 1
    user.discord_id = "123456789"
    user.email = "test@example.com"
    user.name = "Test User"
    user.asu_id = "1234567890"
    user.academic_standing = "Senior"
    user.major = "Computer Science"
    return user


@pytest.fixture
def mock_membership():
    """Create a mock user organization membership."""
    membership = MagicMock()
    membership.id = 1
    membership.user_id = 1
    membership.organization_id = 1
    membership.is_active = True
    membership.joined_at = datetime.utcnow()
    return membership


@pytest.fixture
def mock_points_records():
    """Create mock points records."""
    records = []
    events = ["Event A", "Event B", "Event C"]
    officers = ["Officer 1", "Officer 2"]
    
    for i in range(5):
        record = MagicMock()
        record.id = i + 1
        record.user_id = 1
        record.organization_id = 1
        record.points = 10 * (i + 1)
        record.event = events[i % len(events)]
        record.awarded_by_officer = officers[i % len(officers)]
        record.timestamp = datetime.utcnow()
        records.append(record)
    
    return records
