# Tests

This directory contains unit and integration tests for the platform.

## Structure

```
tests/
├── __init__.py                      # Test module initialization
├── conftest.py                      # Pytest fixtures and configuration
├── test_storefront_api.py           # Business logic tests for storefront points endpoint
└── README.md                        # This file
```

## Running Tests

### Locally (requires dependencies)
```bash
# Install dependencies using uv (recommended)
uv sync

# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_storefront_api.py -v

# Run specific test class
uv run pytest tests/test_storefront_api.py::TestStorefrontPointsEndpointImplementation -v
```

### Via CI (GitHub Actions)
Tests run automatically on:
- Every push to any branch
- Every pull request
- See `.github/workflows/pytest.yml` for configuration

## Test Categories

### Storefront API Tests (`test_storefront_api.py`)
Tests verify the actual implementation of the points endpoint by inspecting source code:

**Implementation Tests**:
- ✅ Endpoint exists and is registered
- ✅ Uses database SUM aggregation for total points (not Python sum)
- ✅ Limits breakdown to 20 records
- ✅ Orders by timestamp descending
- ✅ Validates organization exists
- ✅ Validates user Discord ID
- ✅ Checks user organization membership
- ✅ Formats timestamps as ISO 8601
- ✅ Handles null timestamps gracefully
- ✅ Uses try/finally to close database sessions
- ✅ Returns correct JSON response structure

**Security Tests**:
- ✅ Has @member_required decorator (authentication required)
- ✅ Has @error_handler decorator
- ✅ Email not in URL path (prevents PII exposure)
- ✅ Uses authenticated context for user identification

**Performance Tests**:
- ✅ Separate optimized queries for total and breakdown
- ✅ Uses database filtering, not Python filtering

## Testing Approach

These tests use **code inspection** to verify implementation rather than mocking:
- Tests use Python's `inspect` module to examine actual source code
- Verifies correct database queries (func.sum, limit, order_by)
- Confirms security measures (decorators, validation)
- Checks performance optimizations (aggregation vs. iteration)

Benefits:
- Tests verify actual implementation, not mocked behavior
- Faster than integration tests (no database/app startup)
- Catches implementation regressions
- Documents expected code patterns

## Writing New Tests

### Example: Testing Implementation with Code Inspection
```python
def test_uses_database_aggregation(self):
    """Verify implementation uses database aggregation."""
    import inspect
    from modules.mymodule.api import my_function
    
    source = inspect.getsource(my_function)
    
    # Verify database aggregation is used
    assert 'func.sum' in source
    assert '.scalar()' in source
```

## Current Test Coverage

### Covered Features
- ✅ Storefront points endpoint business logic
- ✅ Security improvements (authentication, no PII in URLs)
- ✅ Performance optimizations (database aggregation, query limiting)
- ✅ Error handling (validation, membership checks)
- ✅ Response formatting (ISO timestamps, null handling)
- ✅ Database session management (proper cleanup)

### Areas for Future Testing
- [ ] Product CRUD operations
- [ ] Order creation and management
- [ ] Cart functionality
- [ ] Member authentication flow
- [ ] Multi-organization support
- [ ] Calendar sync operations

## Dependencies

Tests require:
- pytest >= 8.4.1 (specified in pyproject.toml)
- All application dependencies (installed via `uv sync`)

## CI/CD Integration

Tests are automatically run via GitHub Actions:
- **Workflow**: `.github/workflows/pytest.yml`
- **Trigger**: On push and pull_request events
- **Environment**: `TESTING=true`
- **Command**: `uv run pytest -v`

## Test Failures

If tests fail in CI:
1. Check GitHub Actions workflow run for error details
2. Verify all dependencies are in `pyproject.toml`
3. Ensure `TESTING=true` environment variable is set
4. Run tests locally with `uv run pytest -v` to reproduce

## Testing Best Practices

1. **Test implementation, not just behavior**: Use code inspection to verify correct patterns
2. **Keep tests fast**: Avoid expensive setup (databases, network calls)
3. **Test edge cases**: Null values, empty lists, missing data
4. **Verify security measures**: Authentication, authorization, input validation
5. **Check performance patterns**: Database aggregation, query optimization
6. **Document expectations**: Use descriptive test names and docstrings
