# Quickstart: Tenancy Isolation

**Feature**: 003-tenancy-isolation
**Date**: 2025-12-27
**Prerequisites**: 001-platform-foundation, 002-auth-rbac

## Quick Start

### 1. Test Multi-Org Isolation

```python
from src.database import SessionLocal
from src.models.org import Org
from src.models.user import User
from src.auth.password import hash_password

session = SessionLocal()

# Create two orgs
org_a = Org(name="Org A", slug="org-a", settings_json={})
org_b = Org(name="Org B", slug="org-b", settings_json={})
session.add_all([org_a, org_b])
session.commit()

# Create users in each org
user_a = User(
    org_id=org_a.id, email="user@org-a.com", name="User A",
    role="ADMIN", password_hash=hash_password("password"), status="ACTIVE"
)
user_b = User(
    org_id=org_b.id, email="user@org-b.com", name="User B",
    role="ADMIN", password_hash=hash_password("password"), status="ACTIVE"
)
session.add_all([user_a, user_b])
session.commit()
```

### 2. Test Org Settings API

```bash
# Login as org-a admin
curl -X POST http://localhost:8000/auth/login \
  -d '{"org_slug": "org-a", "email": "user@org-a.com", "password": "password"}'

TOKEN_A="..."

# Get current settings
curl -X GET http://localhost:8000/org/settings \
  -H "Authorization: Bearer $TOKEN_A"

# Update settings
curl -X PATCH http://localhost:8000/org/settings \
  -H "Authorization: Bearer $TOKEN_A" \
  -d '{
    "default_currency": "CHF",
    "matching": {"auto_apply_threshold": 0.95}
  }'
```

### 3. Verify Cross-Org Isolation

```bash
# Create resource as org-a
curl -X POST http://localhost:8000/customers \
  -H "Authorization: Bearer $TOKEN_A" \
  -d '{"name": "Customer A", "default_currency": "EUR", "default_language": "de-DE"}'

# Save customer ID: CUSTOMER_ID_A

# Login as org-b
curl -X POST http://localhost:8000/auth/login \
  -d '{"org_slug": "org-b", "email": "user@org-b.com", "password": "password"}'

TOKEN_B="..."

# Try to access org-a's customer (should return 404, not 403)
curl -X GET http://localhost:8000/customers/$CUSTOMER_ID_A \
  -H "Authorization: Bearer $TOKEN_B"

# Expected: 404 Not Found
```

## Testing Scoped Queries

```python
from src.tenancy.middleware import get_scoped_session, scoped_query
from src.models.customer import Customer

# Scoped session for org_a
session_a = get_scoped_session(org_a.id)

# This query automatically filters by org_a.id
customers = scoped_query(session_a, Customer).all()
assert all(c.org_id == org_a.id for c in customers)
```

## Troubleshooting

**Settings update rejected**: Ensure JSON matches Pydantic schema (check ranges, types).

**Cross-org access returns 200 instead of 404**: Verify scoped_query is used, not raw query.

**Background job accesses wrong org**: Ensure org_id is passed explicitly to task.
