# Quickstart: Authentication & RBAC

**Feature**: 002-auth-rbac
**Date**: 2025-12-27
**Prerequisites**: 001-platform-foundation completed

## Quick Start

### 1. Run Migrations

```bash
cd backend
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Create user and audit tables
```

### 2. Generate Secrets

```bash
# Generate JWT secret
python -c "import secrets; print(f'JWT_SECRET_KEY={secrets.token_urlsafe(32)}')" >> .env

# Generate password pepper
python -c "import secrets; print(f'PASSWORD_PEPPER={secrets.token_urlsafe(32)}')" >> .env
```

### 3. Create Test Admin User

```python
python
```

```python
from src.database import SessionLocal
from src.models.org import Org
from src.models.user import User
from src.auth.password import hash_password

session = SessionLocal()

# Get test org (from 001-platform-foundation)
org = session.query(Org).filter(Org.slug == "test-org").first()

# Create admin user
admin = User(
    org_id=org.id,
    email="admin@test-org.com",
    name="Test Admin",
    role="ADMIN",
    password_hash=hash_password("password123"),
    status="ACTIVE"
)
session.add(admin)
session.commit()
print(f"Created admin user: {admin.id}")
```

### 4. Test Login (via curl)

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "org_slug": "test-org",
    "email": "admin@test-org.com",
    "password": "password123"
  }'
```

Expected response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 5. Test Authenticated Endpoint

```bash
# Save token from previous response
TOKEN="eyJ..."

curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

Expected response:
```json
{
  "user": {
    "id": "uuid",
    "email": "admin@test-org.com",
    "name": "Test Admin",
    "role": "ADMIN",
    "org_id": "uuid",
    "status": "ACTIVE"
  }
}
```

## Testing RBAC

### Create Users with Different Roles

```python
from src.database import SessionLocal
from src.models.user import User
from src.auth.password import hash_password

session = SessionLocal()
org_id = "your-org-uuid"

roles = ["INTEGRATOR", "OPS", "VIEWER"]
for role in roles:
    user = User(
        org_id=org_id,
        email=f"{role.lower()}@test-org.com",
        name=f"Test {role}",
        role=role,
        password_hash=hash_password("password123"),
        status="ACTIVE"
    )
    session.add(user)

session.commit()
```

### Test Permission Denied

```bash
# Login as VIEWER
curl -X POST http://localhost:8000/auth/login \
  -d '{"org_slug": "test-org", "email": "viewer@test-org.com", "password": "password123"}'

# Try to create user (should fail with 403)
VIEWER_TOKEN="..."
curl -X POST http://localhost:8000/users \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -d '{"email": "new@test.com", "name": "New", "role": "OPS", "password": "pass123"}'
```

Expected response: `403 Forbidden`

## Verify Audit Log

```sql
-- Check audit log entries
SELECT
  action,
  actor_id,
  metadata_json->>'email' as email,
  created_at
FROM audit_log
WHERE org_id = 'your-org-uuid'
ORDER BY created_at DESC
LIMIT 10;
```

## Troubleshooting

**Login fails with "Invalid credentials"**:
- Verify org_slug is correct
- Check password hash was generated correctly
- Ensure user.status = 'ACTIVE'

**JWT validation fails**:
- Verify JWT_SECRET_KEY in .env matches the secret used to generate tokens
- Check token hasn't expired (60 minute TTL)
- Ensure Authorization header format: `Bearer <token>`

**Argon2 errors**:
- Ensure argon2-cffi is installed: `pip install argon2-cffi`
- Verify PASSWORD_PEPPER is set in environment

## Next Steps

- Implement 003-tenancy-isolation (org scoping middleware)
- Add user management UI endpoints
- Implement password reset flow (future)
