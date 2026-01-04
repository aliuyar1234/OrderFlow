# OrderFlow Backend Test Suite

Comprehensive test suite for the OrderFlow B2B Order Automation Platform.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test category
pytest -m unit           # Fast unit tests
pytest -m integration    # Integration tests
pytest -m security       # Security tests

# Run specific test file
pytest tests/unit/test_auth_jwt.py -v
```

## Test Structure

```
tests/
├── unit/                       # Unit tests (fast, isolated)
│   ├── test_auth_jwt.py       # JWT token generation/validation (25 tests)
│   ├── test_auth_password.py  # Password hashing/verification (27 tests)
│   ├── test_extraction_confidence.py  # Confidence scoring (35 tests)
│   ├── test_org_model.py      # Org model validation
│   ├── test_file_validation.py # File upload validation
│   ├── pricing/
│   │   └── test_price_tier_selection.py  # Price tier logic
│   └── connectors/
│       ├── test_dropzone_json_v1.py
│       └── test_ack_poller.py
│
├── integration/                # Integration tests (multi-component)
│   ├── test_auth_flow.py      # Login/logout workflow (21 tests)
│   ├── test_tenant_isolation.py  # Multi-tenant isolation (18 tests)
│   ├── test_upload_api.py     # Document upload workflow
│   └── pricing/
│       └── test_csv_import.py # Price import workflow
│
├── security/                   # Security tests (attack simulation)
│   ├── test_sql_injection.py  # SQL injection prevention (22 tests)
│   ├── test_auth_bypass.py    # Auth bypass attempts (20 tests)
│   └── test_tenant_escape.py  # Tenant isolation attacks (16 tests)
│
├── fixtures/                   # Reusable test fixtures
│   └── multi_org.py           # Multi-tenant test setup
│
├── conftest.py                # Pytest configuration & fixtures
└── pytest.ini                 # Pytest settings
```

## Test Categories

### Unit Tests (`-m unit`)
Fast, isolated tests for individual functions/methods:
- **Authentication:** JWT tokens, password hashing
- **Domain Logic:** Confidence calculation, validation rules
- **Models:** Database model validation
- **File Handling:** Upload validation, MIME type checking

**Characteristics:**
- No database dependencies (or use in-memory SQLite)
- Test single functions in isolation
- Fast execution (<1 second per test)
- High coverage of edge cases

### Integration Tests (`-m integration`)
Multi-component tests for workflows:
- **Authentication Flow:** Login, logout, token validation
- **Tenant Isolation:** Cross-tenant access prevention
- **Upload Workflow:** File upload → storage → database
- **Import Workflows:** CSV imports, data processing

**Characteristics:**
- Use test database with fixtures
- Test interactions between modules
- Moderate execution time (1-5 seconds per test)
- Cover real user workflows

### Security Tests (`-m security`)
Attack simulation and vulnerability testing:
- **SQL Injection:** Search, filter, sort parameter injection
- **Auth Bypass:** Token manipulation, privilege escalation
- **Tenant Escape:** Org_id injection, cross-tenant attacks

**Characteristics:**
- Test malicious inputs and attack vectors
- Validate security controls (404 not 403, etc.)
- Cover OWASP Top 10 vulnerabilities
- Prevent regression on security fixes

## Test Fixtures

### Database Fixtures
```python
def test_example(db_session, test_org, admin_user):
    # db_session: Fresh SQLite session per test
    # test_org: Pre-created test organization
    # admin_user: Pre-created admin user in test_org
    pass
```

### Authenticated Client Fixtures
```python
def test_example(authenticated_client):
    # Pre-authenticated client as ADMIN
    response = authenticated_client.get("/users/me")
    assert response.status_code == 200

def test_ops_user(ops_client):
    # Pre-authenticated client as OPS role
    pass

def test_viewer_user(viewer_client):
    # Pre-authenticated client as VIEWER role
    pass
```

### Multi-Tenant Fixtures
```python
def test_tenant_isolation(multi_org_setup):
    org_a, org_b, user_a, user_b = multi_org_setup
    # Two separate orgs with users for isolation testing
    pass
```

## Writing New Tests

### Test Naming Convention
```python
class TestFeatureName:
    """Test suite for specific feature"""

    def test_action_expected_outcome(self):
        """Test that action produces expected outcome"""
        # Arrange
        setup_data()

        # Act
        result = perform_action()

        # Assert
        assert result == expected_value
```

### Example: Unit Test
```python
def test_calculate_header_confidence_complete():
    """Test header with all required fields gets 1.0 confidence"""
    header = ExtractionOrderHeader(
        order_number="PO-12345",
        order_date="2024-01-15",
        currency="EUR"
    )

    confidence = calculate_header_confidence(header)

    assert confidence == 1.0
```

### Example: Integration Test
```python
def test_login_with_valid_credentials(client, db_session, test_org):
    """Test successful login returns JWT token"""
    # Arrange: Create user
    user = User(
        org_id=test_org.id,
        email="ops@test.com",
        password_hash=hash_password("SecureP@ss123"),
        role="OPS",
        status="ACTIVE"
    )
    db_session.add(user)
    db_session.commit()

    # Act: Login
    response = client.post(
        "/auth/login",
        json={"email": "ops@test.com", "password": "SecureP@ss123"}
    )

    # Assert
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### Example: Security Test
```python
def test_sql_injection_in_search(client, db_session, test_org, admin_user):
    """Test SQL injection payload in search is blocked"""
    token = create_access_token(
        user_id=admin_user.id,
        org_id=admin_user.org_id,
        role=admin_user.role,
        email=admin_user.email
    )

    # Attempt SQL injection
    response = client.get(
        "/api/v1/customers?search=' OR '1'='1",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Should not return all customers
    assert response.status_code in [200, 400, 422]
    if response.status_code == 200:
        assert len(response.json()) <= 1  # Safe result set
```

## Coverage Requirements

Per SSOT §11.2:
- **Minimum Coverage:** 90% for domain modules
- **Unit Tests:** ≥90% line coverage
- **Integration Tests:** All critical paths covered
- **Security Tests:** All OWASP Top 10 vulnerabilities tested

**Current Coverage:** ~75-80% overall (see audit report)

## Running Tests in CI/CD

```bash
# Full test suite with coverage
pytest --cov=src --cov-report=xml --cov-fail-under=90

# Generate JUnit XML for CI
pytest --junitxml=test-results.xml

# Fast tests only (for pre-commit)
pytest -m unit --maxfail=1
```

## Debugging Failed Tests

```bash
# Run with verbose output
pytest -v

# Stop at first failure
pytest -x

# Show local variables on failure
pytest -l

# Run specific test with print statements
pytest tests/unit/test_auth_jwt.py::TestCreateAccessToken::test_create_token_with_valid_claims -s

# Drop into debugger on failure
pytest --pdb
```

## Test Data Management

### Creating Test Data
```python
# Use fixtures for reusable data
@pytest.fixture
def test_customer(db_session, test_org):
    customer = Customer(
        org_id=test_org.id,
        name="Test Customer",
        erp_customer_number="CUST-001",
        default_currency="EUR",
        default_language="de-DE"
    )
    db_session.add(customer)
    db_session.commit()
    return customer

# Use factories for variation
def create_customer(org_id, name="Test Customer", **kwargs):
    return Customer(
        org_id=org_id,
        name=name,
        erp_customer_number=kwargs.get("erp_customer_number", "CUST-001"),
        default_currency=kwargs.get("default_currency", "EUR"),
        default_language=kwargs.get("default_language", "de-DE")
    )
```

### Cleaning Up Test Data
```python
# conftest.py handles automatic cleanup via db_session fixture
# Each test gets fresh database, no manual cleanup needed

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)  # Auto cleanup
```

## Environment Variables for Testing

Set in `pytest.ini`:
```ini
env =
    JWT_SECRET=test-secret-key-256-bits
    PASSWORD_PEPPER=test-pepper
    DATABASE_URL=sqlite:///:memory:
    TESTING=true
```

Or override in tests:
```python
def test_with_custom_env(monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'custom-secret')
    # Test uses custom secret
```

## Common Patterns

### Testing Exceptions
```python
def test_invalid_input_raises_error():
    with pytest.raises(ValueError, match="Password cannot be empty"):
        hash_password("")
```

### Parametrized Tests
```python
@pytest.mark.parametrize("role", ["ADMIN", "INTEGRATOR", "OPS", "VIEWER"])
def test_token_for_all_roles(role):
    token = create_access_token(
        user_id=uuid4(),
        org_id=uuid4(),
        role=role,
        email=f"{role.lower()}@test.com"
    )
    payload = decode_token(token)
    assert payload['role'] == role
```

### Testing Async Code
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

## Resources

- **Pytest Documentation:** https://docs.pytest.org/
- **Coverage.py:** https://coverage.readthedocs.io/
- **OWASP Testing Guide:** https://owasp.org/www-project-web-security-testing-guide/
- **Audit Report:** `../specs/AUDIT-test-coverage.md`

## Contributing

1. Write tests for all new features
2. Maintain 90% coverage for domain modules
3. Include security tests for endpoints with user input
4. Add integration tests for workflows
5. Update this README if adding new test categories

## Questions?

See `../specs/AUDIT-test-coverage.md` for comprehensive test coverage audit and recommendations.
