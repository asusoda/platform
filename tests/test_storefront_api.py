import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, g, session
from modules.storefront.api import storefront_blueprint
from modules.storefront.models import Product, Order, OrderItem
from modules.organizations.models import Organization
from modules.points.models import User, UserOrganizationMembership, Points
from modules.utils.db import DBConnect
from datetime import datetime
import json
import os
import tempfile


@pytest.fixture
def app():
    """Create and configure a test Flask app"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.register_blueprint(storefront_blueprint, url_prefix='/storefront')
    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def test_db():
    """Create a test database"""
    # Use in-memory SQLite database for testing
    db_connect = DBConnect("sqlite:///:memory:")
    db = next(db_connect.get_db())
    yield db
    db.close()


@pytest.fixture
def mock_organization(test_db):
    """Create a real organization in test database"""
    org = Organization(
        id=1,
        name="Test Org",
        prefix="test",
        description="Test Organization",
        guild_id="123456789",
        is_active=True
    )
    test_db.add(org)
    test_db.commit()
    return org


@pytest.fixture
def mock_user_clerk(test_db, mock_organization):
    """Create a real user with Clerk authentication in test database"""
    user = User(
        id=1,
        email="test@example.com",
        name="Test User",
        discord_id=None
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def mock_user_discord(test_db, mock_organization):
    """Create a real user with Discord authentication in test database"""
    user = User(
        id=2,
        email="discord@example.com",
        name="Discord User",
        discord_id="987654321"
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def mock_product(test_db, mock_organization):
    """Create a real product in test database"""
    product = Product(
        id=1,
        name="Test Product",
        description="A test product",
        price=10.0,
        stock=100,
        image_url="https://example.com/image.jpg",
        organization_id=mock_organization.id
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def mock_order(test_db, mock_organization, mock_user_clerk):
    """Create a real order in test database"""
    order = Order(
        id=1,
        user_id=mock_user_clerk.id,
        total_amount=20.0,
        status='pending',
        message=None,
        organization_id=mock_organization.id
    )
    test_db.add(order)
    test_db.commit()
    return order


class TestDualAuthDecorator:
    """Test the dual_auth_required decorator"""
    
    def test_no_auth_fails(self, client):
        """Test that request without authentication fails"""
        response = client.get('/storefront/test/orders')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Authentication required' in data.get('message', '')
    
    @patch('modules.storefront.api.verify_clerk_token')
    @patch('modules.storefront.api.db_connect')
    def test_clerk_auth_accepted(self, mock_db_connect, mock_verify, client):
        """Test that Clerk authentication is accepted"""
        mock_verify.return_value = "test@example.com"
        mock_db = MagicMock()
        mock_db_connect.return_value.get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.get(
            '/storefront/test/orders',
            headers={'Authorization': 'Bearer clerk-token-123'}
        )
        
        # Should not return 401 (auth passed)
        assert response.status_code in [200, 404]
        mock_verify.assert_called_once_with('clerk-token-123')
    
    @patch('modules.storefront.api.tokenManger')
    @patch('modules.storefront.api.db_connect')
    def test_discord_auth_accepted(self, mock_db_connect, mock_token_mgr, client):
        """Test that Discord authentication is accepted"""
        mock_token_mgr.is_token_valid.return_value = True
        mock_token_mgr.is_token_expired.return_value = False
        mock_db = MagicMock()
        mock_db_connect.return_value.get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.get(
            '/storefront/test/orders',
            headers={'Authorization': 'Bearer discord-token-123'}
        )
        
        # Should not return 401 (auth passed)
        assert response.status_code in [200, 404]


class TestProductEndpoints:
    """Test product-related endpoints"""
    
    @patch('modules.storefront.api.db_connect')
    def test_get_products_public(self, mock_db_connect, client, mock_organization, mock_product):
        """Test getting products without authentication (public endpoint)"""
        mock_db = MagicMock()
        mock_db_connect.return_value.get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.first.return_value = mock_organization
        mock_db_connect.return_value.get_storefront_products.return_value = [mock_product]
        
        response = client.get('/storefront/test/products')
        
        assert response.status_code == 200
    
    @patch('modules.storefront.api.verify_clerk_token')
    def test_create_product_requires_auth(self, mock_verify, client):
        """Test creating product requires authentication"""
        mock_verify.return_value = None  # No valid token
        
        product_data = {
            'name': 'New Product',
            'description': 'New Description',
            'price': 15.0,
            'stock': 50
        }
        
        response = client.post(
            '/storefront/test/products',
            json=product_data
        )
        
        assert response.status_code == 401
    
    @patch('modules.storefront.api.verify_clerk_token')
    @patch('modules.storefront.api.db_connect')
    def test_create_product_missing_fields(self, mock_db_connect, mock_verify, client):
        """Test creating product with missing required fields fails"""
        mock_verify.return_value = "admin@example.com"
        
        response = client.post(
            '/storefront/test/products',
            json={'name': 'Incomplete Product'},
            headers={'Authorization': 'Bearer clerk-token'}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestOrderEndpoints:
    """Test order-related endpoints"""
    
    def test_create_order_requires_auth(self, client):
        """Test creating order requires authentication"""
        order_data = {
            'total_amount': 10.0,
            'items': [{'product_id': 1, 'quantity': 1, 'price': 10.0}]
        }
        
        response = client.post(
            '/storefront/test/orders',
            json=order_data
        )
        
        assert response.status_code == 401
    
    def test_create_order_missing_items(self, client):
        """Test creating order with missing items fails"""
        with patch('modules.storefront.api.verify_clerk_token') as mock_verify:
            mock_verify.return_value = "test@example.com"
            
            response = client.post(
                '/storefront/test/orders',
                json={'total_amount': 10.0},
                headers={'Authorization': 'Bearer clerk-token'}
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'error' in data


class TestWalletEndpoints:
    """Test wallet/points endpoints"""
    
    def test_get_wallet_requires_auth(self, client):
        """Test getting wallet requires authentication"""
        response = client.get('/storefront/test/wallet/test@example.com')
        assert response.status_code == 401
    
    def test_get_wallet_unauthorized_email(self, client):
        """Test getting wallet with mismatched email fails"""
        with patch('modules.storefront.api.verify_clerk_token') as mock_verify:
            mock_verify.return_value = "test@example.com"
            
            response = client.get(
                '/storefront/test/wallet/other@example.com',
                headers={'Authorization': 'Bearer clerk-token'}
            )
            
            assert response.status_code == 403
            data = json.loads(response.data)
            assert 'Unauthorized' in data.get('error', '')


class TestCheckoutEndpoint:
    """Test checkout endpoint"""
    
    def test_checkout_requires_auth(self, client):
        """Test checkout requires authentication"""
        checkout_data = {
            'total_amount': 10.0,
            'items': [{'product_id': 1, 'quantity': 1, 'price': 10.0}]
        }
        
        response = client.post(
            '/storefront/test/checkout',
            json=checkout_data
        )
        
        assert response.status_code == 401


class TestPublicEndpoints:
    """Test public endpoints (no auth required)"""
    
    @patch('modules.storefront.api.db_connect')
    def test_get_store_products(self, mock_db_connect, client, mock_organization, mock_product):
        """Test getting store products (public endpoint)"""
        mock_db = MagicMock()
        mock_db_connect.return_value.get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.first.return_value = mock_organization
        mock_db_connect.return_value.get_storefront_products.return_value = [mock_product]
        
        response = client.get('/storefront/test/store')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'organization' in data
        assert 'products' in data
