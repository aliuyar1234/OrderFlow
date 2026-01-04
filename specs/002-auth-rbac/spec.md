# Feature Specification: Authentication & RBAC

**Feature Branch**: `002-auth-rbac`
**Created**: 2025-12-27
**Status**: Draft
**Module**: auth, audit
**SSOT References**: §5.2.1 (Roles), §5.4.2 (user table), §8.3 (Auth Endpoints), §11.1 (Auth & Password), §11.2 (RBAC), §11.4 (Audit Logging)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - User Login (Priority: P1)

As an Ops user, I need to log in with my email and password so that I can access the OrderFlow system securely.

**Why this priority**: Authentication is the gateway to the system. Without it, no other functionality is accessible.

**Independent Test**: Can be fully tested by creating a test user, calling the login endpoint with valid credentials, receiving a JWT token, and using that token to access a protected endpoint. Delivers secure access to the system.

**Acceptance Scenarios**:

1. **Given** a user with valid credentials exists, **When** I POST to `/auth/login` with correct org_slug, email, and password, **Then** I receive a JWT access token and user information
2. **Given** a user with valid credentials exists, **When** I POST to `/auth/login` with incorrect password, **Then** I receive a 401 Unauthorized error
3. **Given** I have a valid JWT token, **When** I include it in the Authorization header of an API request, **Then** the request is authenticated and processed
4. **Given** I have an expired JWT token, **When** I use it to access a protected endpoint, **Then** I receive a 401 Unauthorized error
5. **Given** a user account is disabled, **When** I attempt to login, **Then** I receive an error indicating the account is disabled

---

### User Story 2 - Role-Based Access Control (Priority: P1)

As a system administrator, I need different user roles with specific permissions so that users can only perform actions appropriate to their role.

**Why this priority**: RBAC is essential for security and operational safety. Without it, any user could perform dangerous operations like pushing orders to ERP.

**Independent Test**: Can be tested by creating users with different roles (ADMIN, OPS, INTEGRATOR, VIEWER), attempting to access role-restricted endpoints, and verifying that only authorized roles can access them.

**Acceptance Scenarios**:

1. **Given** I am logged in as an ADMIN user, **When** I attempt to access any endpoint, **Then** the request is authorized
2. **Given** I am logged in as an OPS user, **When** I attempt to approve a draft order, **Then** the request is authorized
3. **Given** I am logged in as a VIEWER user, **When** I attempt to modify a draft order, **Then** I receive a 403 Forbidden error
4. **Given** I am logged in as an INTEGRATOR user, **When** I attempt to configure connectors, **Then** the request is authorized
5. **Given** I am logged in as an OPS user, **When** I attempt to create new users, **Then** I receive a 403 Forbidden error (only ADMIN allowed)

---

### User Story 3 - User Management (Priority: P2)

As an ADMIN user, I need to create, update, and disable user accounts so that I can manage who has access to the system.

**Why this priority**: While not required for the basic happy path, user management is essential for operational deployment in a real organization.

**Independent Test**: Can be tested by logging in as ADMIN, creating a new user, verifying they can log in, disabling the account, and verifying login is blocked.

**Acceptance Scenarios**:

1. **Given** I am logged in as ADMIN, **When** I create a new user with email, name, and role, **Then** the user is created with a secure password hash
2. **Given** a user exists, **When** an ADMIN updates their role, **Then** the role is changed and takes effect immediately
3. **Given** a user exists, **When** an ADMIN disables the account, **Then** the user can no longer log in
4. **Given** I am logged in as ADMIN, **When** I retrieve my user profile, **Then** I see my user information including role and last_login_at
5. **Given** I create a user with an email that already exists in my org, **When** I attempt to create it, **Then** I receive a conflict error

---

### User Story 4 - Audit Trail for Security Events (Priority: P2)

As an ADMIN, I need to see a log of login attempts and security-related actions so that I can monitor for suspicious activity and comply with security requirements.

**Why this priority**: Audit logging is crucial for security compliance and debugging, but the system can function without it initially.

**Independent Test**: Can be tested by performing various actions (login success, login failure, role changes), then querying the audit log and verifying all events were recorded.

**Acceptance Scenarios**:

1. **Given** a user successfully logs in, **When** I query the audit log, **Then** I see a LOGIN_SUCCESS event with the user's ID and timestamp
2. **Given** someone attempts to login with invalid credentials, **When** I query the audit log, **Then** I see a LOGIN_FAILED event with the attempted email
3. **Given** an ADMIN creates a new user, **When** I query the audit log, **Then** I see a USER_CREATED event with the new user's ID
4. **Given** an ADMIN changes a user's role, **When** I query the audit log, **Then** I see a USER_ROLE_CHANGED event with old and new roles
5. **Given** an ADMIN disables a user account, **When** I query the audit log, **Then** I see a USER_DISABLED event

---

### Edge Cases

- What happens when a user exists in multiple orgs with different roles (cross-tenant access attempt)?
- How does the system handle concurrent login attempts from the same user?
- What happens when JWT secret key is rotated (invalidating all existing tokens)?
- How does the system handle brute-force login attempts?
- What happens when attempting to disable the last ADMIN user in an org?
- How does the system handle special characters or very long passwords?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST hash passwords using Argon2id with per-user salt and global PASSWORD_PEPPER
- **FR-002**: System MUST issue JWT access tokens with configurable TTL (default 60 minutes)
- **FR-003**: System MUST enforce org isolation - users can only authenticate to their own org_id
- **FR-004**: System MUST support four roles: ADMIN, INTEGRATOR, OPS, VIEWER (as per SSOT §5.2.1)
- **FR-005**: System MUST validate JWT tokens on all protected endpoints
- **FR-006**: System MUST enforce role-based access control according to the permission matrix in SSOT §11.2
- **FR-007**: System MUST update user.last_login_at timestamp on successful login
- **FR-008**: System MUST prevent login for users with status=DISABLED
- **FR-009**: System MUST log all login attempts (success and failure) to audit_log
- **FR-010**: System MUST enforce unique email addresses per org (case-insensitive)
- **FR-011**: System MUST provide endpoints for user CRUD operations (restricted to ADMIN role)
- **FR-012**: System MUST store user email addresses as CITEXT (case-insensitive text)
- **FR-013**: System MUST prevent disabling the last ADMIN user in an org. Attempting to disable returns 400 Bad Request with message 'Cannot disable last admin user. Assign another user to ADMIN role first.'
- **FR-014**: System MUST expose Prometheus metrics endpoint with: auth_login_attempts_total{org_id,status}, auth_failed_logins_total{org_id,reason}, auth_token_validation_duration_ms{org_id}. All auth operations MUST be covered by OpenTelemetry spans.

### Role Permission Matrix (SSOT §11.2)

- **ADMIN**: Full access to all operations
- **INTEGRATOR**: Access to imports, connectors, ai monitor, view audit, view drafts
- **OPS**: Access to inbox/drafts/mappings (read/write), approve/push operations
- **VIEWER**: Read-only access to inbox/drafts/mappings

### Key Entities

- **User**: Represents a person who can access the system. Each user belongs to one organization, has a role, and authenticates with email/password. The system stores Argon2id password hashes, never plaintext passwords.

- **AuditLog**: Immutable record of security-relevant events (login attempts, user changes, etc.). Each entry includes actor (user_id or null for anonymous), action type, timestamp, and metadata.

### Technical Constraints

- **TC-001**: JWT tokens MUST include claims: user_id, org_id, role, exp (expiration)
- **TC-002**: JWT tokens MUST be signed with HS256 or RS256 algorithm
- **TC-003**: Password hashing MUST use Argon2id (not bcrypt or PBKDF2)
- **TC-004**: User email field MUST use PostgreSQL CITEXT type for case-insensitive uniqueness
- **TC-005**: Audit log entries MUST be append-only (no updates or deletes)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Login endpoint responds in under 500ms for valid credentials (P95)
- **SC-002**: JWT token validation adds less than 10ms overhead to protected endpoint requests (P95)
- **SC-003**: 100% of security events (login, user changes) are recorded in audit log
- **SC-004**: Zero successful cross-tenant authentication attempts (verified by automated tests)
- **SC-005**: Password hashing withstands minimum 1 billion hash attempts per second brute force
- **SC-006**: Zero permission bypass vulnerabilities (verified by role-based integration tests)

### Security Validation

- **SV-001**: Argon2id configuration meets OWASP recommendations (memory cost, iterations)
- **SV-002**: JWT secret is cryptographically secure (minimum 256 bits)
- **SV-003**: Failed login attempts do not leak information about user existence
- **SV-004**: Password change/reset invalidates old tokens (if implemented)

## Dependencies

- **Depends on**: 001-platform-foundation (org table, database setup)
- **Dependency reason**: Auth requires org table for multi-tenant isolation and user.org_id foreign key

## Implementation Notes

### User Table Schema (SSOT §5.4.2)

```sql
CREATE TABLE "user" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  email CITEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('ADMIN', 'INTEGRATOR', 'OPS', 'VIEWER')),
  password_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DISABLED')),
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, email)
);

CREATE INDEX idx_user_org_role ON "user"(org_id, role);
```

### JWT Token Claims

```json
{
  "sub": "user_id (UUID)",
  "org_id": "org_id (UUID)",
  "role": "ADMIN|INTEGRATOR|OPS|VIEWER",
  "email": "user@example.com",
  "exp": 1735300000
}
```

### Audit Log Schema

```sql
CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  actor_id UUID REFERENCES "user"(id),  -- NULL for anonymous (failed logins)
  action TEXT NOT NULL,  -- 'LOGIN_SUCCESS', 'LOGIN_FAILED', 'USER_CREATED', etc.
  entity_type TEXT,  -- 'user', 'draft_order', etc.
  entity_id UUID,
  metadata_json JSONB,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_org_created ON audit_log(org_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_log(actor_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
```

### Password Security (SSOT §11.1)

- Use Argon2id with recommended parameters:
  - Memory cost: 64 MB minimum
  - Time cost: 3 iterations minimum
  - Parallelism: 4 threads
- Per-user salt is generated automatically by Argon2id
- Global PASSWORD_PEPPER environment variable adds additional security layer
- Password hash format: `$argon2id$v=19$m=65536,t=3,p=4$...$...`

### API Endpoints (SSOT §8.3)

#### POST `/auth/login`
```json
// Request
{
  "org_slug": "acme",
  "email": "ops@acme.de",
  "password": "secret"
}

// Response 200
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}

// Response 401
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password"
  }
}
```

#### GET `/auth/me`
```json
// Response 200
{
  "user": {
    "id": "uuid",
    "email": "ops@acme.de",
    "name": "John Doe",
    "role": "OPS",
    "org_id": "uuid",
    "last_login_at": "2025-12-27T10:00:00Z"
  }
}
```

### RBAC Middleware

Implement decorator/middleware for endpoint protection:

```python
@require_role(["ADMIN", "OPS"])
async def approve_draft_order(...):
    ...

@require_role(["ADMIN"])
async def create_user(...):
    ...
```

### Rate Limiting (Optional for MVP)

Consider implementing rate limiting for login endpoint to prevent brute force:
- 5 failed attempts per email per 15 minutes
- Exponential backoff after repeated failures

## Out of Scope

- Refresh tokens (MVP optional, per SSOT §11.1)
- OAuth/SSO integration (future extension)
- Multi-factor authentication (future extension)
- Password reset via email (future extension)
- Session management / concurrent session limits
- Advanced brute-force protection (basic rate limiting only)
- Password complexity requirements (implement in UI, not backend MVP)

## Testing Strategy

### Unit Tests
- Password hashing and verification
- JWT token generation and validation
- Role permission checks
- Email normalization (case-insensitivity)
- Password hash format validation

### Integration Tests
- Login flow with valid credentials
- Login rejection for invalid credentials
- Login rejection for disabled users
- JWT token validation on protected endpoints
- Role-based access control for each endpoint
- Cross-tenant authentication blocking
- Audit log entry creation for all security events
- Unique email constraint per org
- Last login timestamp updates

### Security Tests
- Timing attack resistance (login should take same time for valid/invalid)
- SQL injection attempts in login fields
- JWT token tampering detection
- Token expiration enforcement
- Cross-org access attempts with valid tokens
- Password hash cracking resistance (automated tools)

### Test Fixtures
- Create users with all four roles
- Create users in multiple orgs with same email
- Create disabled user accounts
- Generate valid and invalid JWT tokens
- Create audit log entries for verification
