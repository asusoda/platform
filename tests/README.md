# Tests

This directory contains unit and integration tests for the platform.

## Structure

```
tests/
├── __init__.py                      # Test module initialization
├── conftest.py                      # Pytest fixtures and configuration
├── test_storefront_points.py        # Unit tests for storefront points endpoint
├── test_storefront_integration.py   # Integration tests for storefront
└── test_frontend_fixes.py           # Documentation of frontend fixes
```

## Running Tests

### Run all tests
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_storefront_points.py -v
```

### Run specific test class
```bash
pytest tests/test_storefront_points.py::TestStorefrontPointsEndpoint -v
```

### Run specific test method
```bash
pytest tests/test_storefront_points.py::TestStorefrontPointsEndpoint::test_get_user_points_success -v
```

### Run with coverage (if pytest-cov is installed)
```bash
pytest --cov=modules --cov-report=html -v
```

## Test Categories

### Unit Tests
- `test_storefront_points.py`: Tests for the GET `/<org_prefix>/members/points` endpoint
  - Tests authentication requirements
  - Tests error conditions (no org, no user, no membership)
  - Tests successful point retrieval
  - Tests database query optimization (aggregation, limiting)
  - Tests response structure

### Integration Tests
- `test_storefront_integration.py`: End-to-end tests for storefront features
  - Tests complete request/response flow
  - Tests decorator application
  - Tests database session cleanup
  - Tests query ordering

### Frontend Tests
- `test_frontend_fixes.py`: Documentation of frontend syntax fixes
  - Documents MemberStorePage.js syntax error fix
  - Provides manual testing instructions

## Writing New Tests

### Test Fixtures
Common fixtures are defined in `conftest.py`:
- `app`: Flask application instance
- `client`: Test client for making requests
- `mock_db_session`: Mock database session
- `mock_organization`: Mock organization object
- `mock_user`: Mock user object
- `mock_membership`: Mock membership object
- `mock_points_records`: Mock points data

### Example Test
```python
import pytest
from unittest.mock import patch, MagicMock

class TestMyFeature:
    @patch('modules.mymodule.api.db_connect')
    def test_my_endpoint(self, mock_db_connect, client):
        # Setup
        mock_db = MagicMock()
        mock_db_connect.get_db.return_value = iter([mock_db])
        
        # Execute
        response = client.get('/api/myendpoint')
        
        # Assert
        assert response.status_code == 200
```

## Current Test Coverage

### Covered Features
- ✅ Storefront points endpoint security (authentication required)
- ✅ Storefront points endpoint error handling
- ✅ Storefront points endpoint database optimization
- ✅ Storefront points endpoint response structure
- ✅ Frontend syntax error fixes (documented)

### Areas for Future Testing
- [ ] Product CRUD operations
- [ ] Order creation and management
- [ ] Cart functionality
- [ ] Member authentication flow
- [ ] Points calculation accuracy
- [ ] Multi-organization support

## Testing Best Practices

1. **Use descriptive test names**: Test names should clearly describe what is being tested
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Mock external dependencies**: Use mocks for database, API calls, etc.
4. **Test edge cases**: Empty data, None values, invalid inputs
5. **Keep tests independent**: Each test should be able to run in isolation
6. **Use fixtures**: Reuse common setup via pytest fixtures
7. **Test both success and failure paths**: Don't just test happy paths

## Dependencies

Tests require:
- pytest >= 9.0.2
- pytest-flask >= 1.3.0
- pytest-mock >= 3.15.1

Install with:
```bash
pip install pytest pytest-flask pytest-mock
```

Or use uv:
```bash
uv sync
```

## CI/CD Integration

Tests are automatically run on:
- Pull request creation
- Push to main branches
- Before deployment

See `.github/workflows/` for CI configuration.
