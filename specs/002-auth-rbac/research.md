# Research: Authentication & RBAC

**Feature**: 002-auth-rbac
**Date**: 2025-12-27
**Status**: Final

## Key Decisions and Rationale

### 1. Argon2id for Password Hashing

**Decision**: Use Argon2id (via argon2-cffi) with OWASP-recommended parameters + global PASSWORD_PEPPER.

**Rationale**:
- **Security**: Winner of Password Hashing Competition 2015, resistant to GPU/ASIC attacks
- **Argon2id variant**: Combines data-dependent (Argon2i) and data-independent (Argon2d) memory access for maximum resistance
- **OWASP parameters**: Memory cost 64MB, time cost 3 iterations, parallelism 4 threads
- **PASSWORD_PEPPER**: Additional secret not stored in database, prevents rainbow tables even if DB compromised

**Configuration**:
```python
from argon2 import PasswordHasher
from argon2.low_level import Type

ph = PasswordHasher(
    time_cost=3,           # iterations
    memory_cost=65536,     # 64 MB
    parallelism=4,         # threads
    hash_len=32,           # output length
    salt_len=16,           # salt length
    type=Type.ID           # Argon2id variant
)
```

**Alternatives Rejected**:
- bcrypt: Less memory-hard, vulnerable to GPU attacks
- PBKDF2: Too fast on modern hardware
- scrypt: Less widely adopted, fewer security audits

**References**:
- SSOT §11.1 (Password Security)
- OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

---

### 2. JWT for Access Tokens (No Refresh Tokens in MVP)

**Decision**: Issue JWT access tokens with 60-minute TTL, signed with HS256. No refresh tokens in MVP.

**Rationale**:
- **Stateless**: No server-side session storage required
- **Scalable**: Works across multiple backend instances without shared state
- **Standard**: Widely supported, well-understood security model
- **Short TTL**: 60 minutes balances security (limited exposure if stolen) vs UX (not too frequent re-login)
- **No refresh tokens**: Simplifies MVP, can add later if needed

**Token Claims**:
```json
{
  "sub": "user_id (UUID)",
  "org_id": "org_id (UUID)",
  "role": "ADMIN|INTEGRATOR|OPS|VIEWER",
  "email": "user@example.com",
  "exp": 1735300000
}
```

**Alternatives Considered**:
- Session cookies: Requires server-side storage (Redis), more complex for API
- OAuth2/OIDC: Overkill for MVP (no third-party integrations yet)
- Refresh tokens: Adds complexity, not needed for 60-minute TTL

**References**:
- SSOT §11.1 (JWT tokens specified)
- RFC 7519 (JWT standard)

---

### 3. Role-Based Access Control (4 Roles)

**Decision**: Implement RBAC with exactly 4 roles as defined in SSOT §5.2.1.

**Roles**:
- **ADMIN**: Full access (user management, settings, all operations)
- **INTEGRATOR**: Technical operations (imports, connectors, monitoring)
- **OPS**: Order processing (inbox, drafts, mappings, approve/push)
- **VIEWER**: Read-only access

**Permission Matrix** (SSOT §11.2):
```python
PERMISSIONS = {
    "ADMIN": ["*"],  # All permissions
    "INTEGRATOR": [
        "imports:read", "imports:write",
        "connectors:read", "connectors:write",
        "ai_monitor:read",
        "audit:read",
        "drafts:read"
    ],
    "OPS": [
        "inbox:read", "inbox:write",
        "drafts:read", "drafts:write",
        "mappings:read", "mappings:write",
        "orders:approve", "orders:push"
    ],
    "VIEWER": [
        "inbox:read",
        "drafts:read",
        "mappings:read"
    ]
}
```

**Enforcement Pattern**:
```python
from functools import wraps
from fastapi import HTTPException, Depends
from src.auth.dependencies import get_current_user

def require_role(allowed_roles: list[str]):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=Depends(get_current_user), **kwargs):
            if current_user.role not in allowed_roles:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# Usage
@router.post("/users")
@require_role(["ADMIN"])
async def create_user(...):
    ...
```

**Rationale**:
- **Simplicity**: 4 roles cover all MVP use cases
- **Clear separation**: Each role has distinct responsibilities
- **Auditable**: Role in JWT claim enables request-level audit

**References**:
- SSOT §5.2.1 (Role enumeration)
- SSOT §11.2 (Permission matrix)

---

### 4. Audit Log for Security Events

**Decision**: Immutable audit_log table tracking all authentication and authorization events.

**Events to Log**:
- LOGIN_SUCCESS / LOGIN_FAILED
- USER_CREATED / USER_UPDATED / USER_DISABLED
- USER_ROLE_CHANGED
- PASSWORD_CHANGED (future)
- PERMISSION_DENIED (403 errors)

**Schema**:
```sql
CREATE TABLE audit_log (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  actor_id UUID,  -- NULL for anonymous (failed logins)
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  metadata_json JSONB,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL
);
```

**Rationale**:
- **Compliance**: Required for security audits, GDPR accountability
- **Forensics**: Essential for investigating security incidents
- **Immutable**: No UPDATE or DELETE operations allowed
- **Retention**: Default 1 year, configurable per compliance needs

**Implementation**:
```python
async def log_audit_event(
    session: Session,
    org_id: UUID,
    action: str,
    actor_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    metadata: dict | None = None,
    request: Request | None = None
):
    audit_entry = AuditLog(
        org_id=org_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata or {},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    session.add(audit_entry)
    session.commit()
```

**References**:
- SSOT §11.4 (Audit Logging)
- SSOT §5.4.16 (audit_log table)

---

### 5. Multi-Tenant Auth via org_slug

**Decision**: Login requires org_slug parameter to select tenant, preventing cross-org authentication.

**Login Flow**:
1. Client sends: `{"org_slug": "acme", "email": "user@acme.com", "password": "..."}`
2. Backend queries: `SELECT * FROM org WHERE slug = 'acme'`
3. Backend queries: `SELECT * FROM user WHERE org_id = <org_id> AND email = 'user@acme.com'`
4. If password matches, generate JWT with org_id claim

**Benefits**:
- **Security**: Impossible to authenticate to wrong org
- **Simplicity**: No separate "select org" step after login
- **Clarity**: JWT always contains correct org_id

**Edge Cases**:
- User exists in multiple orgs with same email → Separate accounts, separate passwords
- Org_slug not found → Same error as invalid credentials (no info leakage)

**References**:
- SSOT §11.2 (Multi-tenant auth enforcement)

---

## Technology Stack Best Practices

### FastAPI Dependency Injection for Auth

**Pattern**:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db_session)
) -> User:
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = UUID(payload["sub"])
        org_id = UUID(payload["org_id"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    user = session.query(User).filter(
        User.id == user_id,
        User.org_id == org_id,
        User.status == "ACTIVE"
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
```

**Usage**:
```python
@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {"user": current_user.to_dict()}
```

---

### Password Hashing with Pepper

**Implementation**:
```python
import os
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER")  # Secret not in DB
ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash password with Argon2id + pepper"""
    peppered = password + PASSWORD_PEPPER
    return ph.hash(peppered)

def verify_password(password: str, hash: str) -> bool:
    """Verify password against hash"""
    try:
        peppered = password + PASSWORD_PEPPER
        ph.verify(hash, peppered)
        return True
    except VerifyMismatchError:
        return False
```

**Environment Variable**:
```bash
# Generate secure pepper (one-time, keep secret)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# In .env
PASSWORD_PEPPER=your_secret_pepper_here_do_not_commit
```

---

### JWT Token Generation

**Implementation**:
```python
from jose import jwt
from datetime import datetime, timedelta
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(user: User) -> str:
    """Generate JWT access token"""
    expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user.id),
        "org_id": str(user.org_id),
        "role": user.role,
        "email": user.email,
        "exp": expires_at
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token
```

**Secret Generation**:
```bash
# Generate secure JWT secret (one-time, keep secret)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# In .env
JWT_SECRET_KEY=your_secret_key_here_minimum_256_bits
```

---

### Timing Attack Prevention

**Problem**: Login endpoint must take same time for valid/invalid credentials to prevent username enumeration.

**Solution**:
```python
import time

async def login(org_slug: str, email: str, password: str):
    # Always hash password (constant time regardless of user existence)
    start_time = time.time()

    # Query user
    user = session.query(User).filter(...).first()

    if user:
        password_valid = verify_password(password, user.password_hash)
    else:
        # Dummy hash to maintain constant timing
        verify_password(password, "$argon2id$v=19$m=65536,t=3,p=4$...")
        password_valid = False

    # Ensure minimum execution time (e.g., 200ms)
    elapsed = time.time() - start_time
    if elapsed < 0.2:
        time.sleep(0.2 - elapsed)

    if not password_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return create_access_token(user)
```

---

## Security Considerations

### Secret Management

**Secrets Required**:
- `JWT_SECRET_KEY`: For signing tokens (minimum 256 bits)
- `PASSWORD_PEPPER`: Additional password protection (minimum 256 bits)
- `DATABASE_URL`: Contains database password

**Best Practices**:
- Use environment variables (never commit)
- Rotate secrets every 90 days in production
- Different secrets for dev/staging/production
- Use secret management service (AWS Secrets Manager, HashiCorp Vault) in production

### Cross-Origin Resource Sharing (CORS)

**Configuration**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production**: Restrict to specific frontend domains only.

### Rate Limiting (Optional for MVP)

**Implementation** (using slowapi):
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/minute")  # 5 login attempts per minute per IP
async def login(...):
    ...
```

---

## Testing Strategy

### Unit Tests

```python
def test_password_hashing():
    password = "secure_password_123"
    hash = hash_password(password)

    assert verify_password(password, hash) is True
    assert verify_password("wrong_password", hash) is False

def test_jwt_token_generation():
    user = User(id=uuid4(), org_id=uuid4(), role="ADMIN", email="test@example.com")
    token = create_access_token(user)

    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "ADMIN"
```

### Integration Tests

```python
def test_login_success(client, test_org, test_user):
    response = client.post("/auth/login", json={
        "org_slug": test_org.slug,
        "email": test_user.email,
        "password": "test_password"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_invalid_credentials(client, test_org):
    response = client.post("/auth/login", json={
        "org_slug": test_org.slug,
        "email": "nonexistent@example.com",
        "password": "wrong"
    })

    assert response.status_code == 401

def test_rbac_enforcement(client, test_viewer_user, test_admin_user):
    # Viewer cannot create users
    viewer_token = login_as_user(client, test_viewer_user)
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"email": "new@example.com", ...}
    )
    assert response.status_code == 403

    # Admin can create users
    admin_token = login_as_user(client, test_admin_user)
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "new@example.com", ...}
    )
    assert response.status_code == 201
```

### Security Tests

```python
def test_token_tampering(client):
    """Verify tampered tokens are rejected"""
    valid_token = create_access_token(test_user)

    # Modify payload
    tampered_token = valid_token[:-10] + "TAMPERED12"

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert response.status_code == 401

def test_cross_org_access(client, org_a_user, org_b_resource):
    """Verify users cannot access other org's resources"""
    token = login_as_user(client, org_a_user)

    response = client.get(
        f"/drafts/{org_b_resource.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    # Must return 404, not 403 (avoid leaking existence)
    assert response.status_code == 404
```

---

## References

- SSOT §5.2.1: Role enumeration
- SSOT §5.4.2: user table schema
- SSOT §8.3: Auth API endpoints
- SSOT §11: Auth, RBAC, Audit
- OWASP: Password Storage Cheat Sheet
- RFC 7519: JSON Web Tokens
- argon2-cffi: https://argon2-cffi.readthedocs.io/
- python-jose: https://python-jose.readthedocs.io/
