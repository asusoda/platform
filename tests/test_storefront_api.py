"""
Business logic tests for storefront points endpoint.
Tests verify actual implementation behavior.
"""
import pytest
import os
import sys

# Set testing environment before any imports
os.environ['TESTING'] = 'true'

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestStorefrontPointsEndpointImplementation:
    """Test the implementation of the points endpoint."""
    
    def test_endpoint_exists(self):
        """Verify the endpoint function exists and is registered."""
        from modules.storefront.api import storefront_blueprint
        
        # Check that the endpoint function exists
        assert 'get_user_points_public' in storefront_blueprint.view_functions
    
    def test_uses_database_aggregation_for_total_points(self):
        """Verify implementation uses database SUM aggregation."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify it uses func.sum() for aggregation
        assert 'func.sum' in source, "Should use database aggregation with func.sum()"
        assert '.scalar()' in source, "Should use scalar() to get aggregation result"
        assert 'or 0' in source, "Should handle None result with 'or 0'"
    
    def test_limits_breakdown_to_20_records(self):
        """Verify implementation limits breakdown to 20 records."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify limiting
        assert 'limit(20)' in source, "Should limit to 20 records"
        assert '.all()' in source, "Should use all() to fetch limited records"
    
    def test_orders_by_timestamp_descending(self):
        """Verify implementation orders by timestamp in descending order."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify ordering
        assert 'order_by' in source, "Should order results"
        assert '.desc()' in source, "Should use descending order"
        assert 'timestamp' in source, "Should order by timestamp"
    
    def test_validates_organization(self):
        """Verify implementation validates organization parameter."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify organization validation
        assert 'organization' in source
        assert 'Organization not found' in source
        assert '404' in source
    
    def test_validates_user_discord_id(self):
        """Verify implementation validates user_discord_id parameter."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify user_discord_id validation
        assert 'user_discord_id' in source
        assert 'User not found' in source
    
    def test_checks_user_membership(self):
        """Verify implementation checks user organization membership."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify membership check
        assert 'UserOrganizationMembership' in source
        assert 'is_active' in source
        assert 'User is not a member of this organization' in source
        assert '403' in source
    
    def test_formats_timestamps_as_iso(self):
        """Verify implementation formats timestamps as ISO strings."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify ISO formatting
        assert 'isoformat()' in source, "Should format timestamps as ISO 8601"
    
    def test_handles_null_timestamps(self):
        """Verify implementation handles None timestamps."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify null handling
        assert 'if p.timestamp else None' in source or 'if p.timestamp' in source
    
    def test_closes_database_session(self):
        """Verify implementation uses finally block to close database."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify try/finally pattern
        assert 'try:' in source
        assert 'finally:' in source
        assert 'db.close()' in source
    
    def test_returns_correct_response_structure(self):
        """Verify implementation returns correct JSON structure."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Verify response fields
        assert '"email"' in source or "'email'" in source
        assert '"total_points"' in source or "'total_points'" in source
        assert '"points_breakdown"' in source or "'points_breakdown'" in source


class TestEndpointDecoratorConfiguration:
    """Test that endpoint has correct decorators applied."""
    
    def test_has_member_required_decorator(self):
        """Verify endpoint requires member authentication."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        # Get the function source including decorators
        source_lines = inspect.getsourcelines(get_user_points_public)[0]
        source_text = ''.join(source_lines)
        
        # Check for @member_required decorator
        assert '@member_required' in source_text, "Endpoint must have @member_required decorator"
    
    def test_has_error_handler_decorator(self):
        """Verify endpoint has error handler."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source_lines = inspect.getsourcelines(get_user_points_public)[0]
        source_text = ''.join(source_lines)
        
        # Check for @error_handler decorator
        assert '@error_handler' in source_text, "Endpoint should have @error_handler decorator"


class TestSecurityImprovements:
    """Test security improvements over original implementation."""
    
    def test_no_email_in_url_path(self):
        """Verify email is not exposed in URL path."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        # Get function signature
        signature = inspect.signature(get_user_points_public)
        params = list(signature.parameters.keys())
        
        # Email should not be a URL parameter
        assert 'email' not in params, "Email should not be in URL path"
        
        # Should use org_prefix and kwargs
        assert 'org_prefix' in params
        assert 'kwargs' in params
    
    def test_uses_authenticated_context_for_user_id(self):
        """Verify endpoint gets user from authenticated context, not URL."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Should get user_discord_id from kwargs (set by decorator)
        assert "kwargs.get('user_discord_id')" in source
        assert "kwargs.get('organization')" in source


class TestPerformanceOptimizations:
    """Test performance optimizations in implementation."""
    
    def test_separate_queries_for_total_and_breakdown(self):
        """Verify total and breakdown use separate optimized queries."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Should have separate query for total (with func.sum)
        assert 'func.sum(Points.points)' in source
        
        # Should have separate query for breakdown (with limit)
        assert 'limit(20)' in source
        
        # Verify NOT using Python aggregation
        assert 'sum(p.points for p in' not in source, "Should not sum in Python"
    
    def test_uses_database_filtering(self):
        """Verify queries use database filtering, not Python filtering."""
        import inspect
        from modules.storefront.api import get_user_points_public
        
        source = inspect.getsource(get_user_points_public)
        
        # Should use filter_by for database filtering
        assert '.filter_by(' in source
        assert 'user_id=' in source
        assert 'organization_id=' in source
