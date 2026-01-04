# Feature Specification: Tenancy Isolation

**Feature Branch**: `003-tenancy-isolation`
**Created**: 2025-12-27
**Status**: Draft
**Module**: tenancy
**SSOT References**: §5.1 (Konventionen), §5.4.1 (org table), §10.1 (Org Settings)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Tenant Scoping (Priority: P1)

As a developer building features, I need all database queries to automatically filter by org_id so that I never accidentally leak data across tenants.

**Why this priority**: Multi-tenant isolation is a critical security requirement. Without automatic enforcement, every query becomes a potential security vulnerability.

**Independent Test**: Can be fully tested by creating test data for multiple orgs, making API calls authenticated as different orgs, and verifying that queries only return data for the authenticated org. Delivers fundamental data security.

**Acceptance Scenarios**:

1. **Given** I am authenticated as Org A, **When** I query any endpoint, **Then** I only see data belonging to Org A
2. **Given** data exists for Org A and Org B, **When** Org A queries for records, **Then** Org B's records are never visible
3. **Given** I attempt to access a resource by ID from another org, **When** the system checks authorization, **Then** I receive a 404 Not Found error (not 403, to avoid leaking existence)
4. **Given** I create a new resource while authenticated as Org A, **When** the resource is saved, **Then** it is automatically tagged with Org A's org_id

---

### User Story 2 - Org Settings Management (Priority: P2)

As an ADMIN user, I need to view and update my organization's settings so that I can configure system behavior specific to my tenant.

**Why this priority**: While the system can operate with defaults, org-specific configuration is essential for production use (currency, price tolerance, AI thresholds).

**Independent Test**: Can be tested by retrieving org settings via API, updating them with new values, and verifying the changes persist and affect system behavior (e.g., matching thresholds).

**Acceptance Scenarios**:

1. **Given** I am logged in as ADMIN, **When** I GET `/org/settings`, **Then** I see my organization's current settings including default_currency, price_tolerance_percent, and matching thresholds
2. **Given** I am logged in as ADMIN, **When** I PATCH `/org/settings` with new matching thresholds, **Then** the settings are updated and immediately affect matching behavior
3. **Given** I update default_currency to CHF, **When** new draft orders are created, **Then** they default to CHF currency
4. **Given** invalid settings are submitted (e.g., negative price tolerance), **When** I attempt to save them, **Then** I receive a validation error
5. **Given** I am logged in as OPS (not ADMIN), **When** I attempt to modify org settings, **Then** I receive a 403 Forbidden error

---

### User Story 3 - Org Isolation in Background Jobs (Priority: P1)

As a system architect, I need background workers (Celery tasks) to respect org_id boundaries so that async processing maintains tenant isolation.

**Why this priority**: Background jobs process sensitive data. Without org_id enforcement, a job could process the wrong org's documents or orders.

**Independent Test**: Can be tested by enqueueing jobs for different orgs, verifying each job only accesses data for its intended org, and confirming no cross-org data access occurs.

**Acceptance Scenarios**:

1. **Given** a document extraction job is enqueued for Org A, **When** the worker processes the job, **Then** it only queries and updates data for Org A
2. **Given** two orgs have documents with the same filename, **When** extraction runs for Org A's document, **Then** it never touches Org B's document
3. **Given** a matching job is processing for Org A, **When** it searches for products, **Then** it only considers Org A's product catalog
4. **Given** org_id is missing from a job payload, **When** the worker attempts to process it, **Then** the job fails with a clear error message

---

### Edge Cases

- What happens when an org_id is somehow NULL in the database?
- How does the system handle org deletion with existing dependent data?
- What happens when JWT contains an org_id that doesn't exist in the database?
- How does the system prevent timing attacks that could leak org existence?
- What happens when background jobs receive org_id for a deleted org?
- How does the system handle concurrent updates to org settings from multiple admins?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically inject org_id filter on all database queries for multi-tenant tables
- **FR-002**: System MUST derive org_id from authenticated user's JWT token for all API requests
- **FR-003**: System MUST pass org_id explicitly to all background job payloads
- **FR-004**: System MUST return 404 Not Found (not 403) when a resource exists but belongs to a different org
- **FR-005**: System MUST validate that org_id in JWT matches an existing org in the database
- **FR-006**: System MUST provide API endpoints to retrieve and update org settings (ADMIN only)
- **FR-007**: System MUST validate org.settings_json against a schema before saving
- **FR-008**: System MUST provide default settings for newly created orgs
- **FR-009**: System MUST enforce that org_id is NOT NULL on all multi-tenant tables (database constraint)
- **FR-010**: System MUST prevent modification of org_id on existing records (immutable after creation)
- **FR-011**: System MUST enforce org_id NOT NULL constraint and foreign key at database level (not just application). Schema validation tests MUST verify all multi-tenant tables have proper constraints.

### Key Entities

- **Organization Settings**: JSON configuration stored in org.settings_json that controls tenant-specific behavior including default currency, price tolerance, matching thresholds, customer detection settings, AI configuration, and extraction parameters. Settings follow the schema defined in SSOT §10.1.

### Technical Constraints

- **TC-001**: Org_id MUST be enforced via foreign key constraints, not just application logic
- **TC-002**: All SELECT queries on multi-tenant tables MUST include WHERE org_id = $1
- **TC-003**: Settings JSON MUST be validated against Pydantic schema before persistence
- **TC-004**: Org_id in API context MUST come from JWT claims, never from request body
- **TC-005**: Background jobs MUST receive org_id as explicit parameter, not derived from global state

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of multi-tenant table queries include org_id filter (verified by SQL query logging)
- **SC-002**: Zero cross-tenant data leaks in automated security tests (1000+ test cases)
- **SC-003**: Org settings updates take effect within 1 second (no cache invalidation lag)
- **SC-004**: 100% of background jobs respect org_id boundaries (verified by integration tests)
- **SC-005**: Database foreign key constraints prevent orphaned org_id references (verified by constraint tests)

### Security Validation

- **SV-001**: Penetration testing confirms no cross-org data access via API manipulation
- **SV-002**: SQL injection attempts cannot bypass org_id filters
- **SV-003**: JWT token tampering (changing org_id) is detected and rejected
- **SV-004**: Background jobs fail safely when org_id is invalid (no fallback to wrong org)

## Dependencies

- **Depends on**: 001-platform-foundation (org table)
- **Depends on**: 002-auth-rbac (JWT with org_id claim)
- **Dependency reason**: Tenancy isolation requires org table to exist and JWT tokens to carry org_id

## Implementation Notes

### Org Scoping Middleware/Decorator

Implement automatic org_id injection for queries:

```python
# Example SQLAlchemy approach
def get_scoped_session(org_id: UUID) -> Session:
    """Returns session that automatically filters by org_id"""
    session = Session()
    # Set org_id in session info
    session.info["org_id"] = org_id
    return session

# Query builder that auto-adds org_id filter
def scoped_query(session: Session, model):
    org_id = session.info.get("org_id")
    if not org_id:
        raise ValueError("org_id not set in session")
    return session.query(model).filter(model.org_id == org_id)
```

### Org Settings Schema (SSOT §10.1)

```python
from pydantic import BaseModel, Field

class MatchingSettings(BaseModel):
    auto_apply_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    auto_apply_gap: float = Field(default=0.10, ge=0.0, le=1.0)

class CustomerDetectionSettings(BaseModel):
    auto_select_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    require_manual_review_if_multiple: bool = True

class AISettings(BaseModel):
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_budget_daily_usd: float = Field(default=10.0, ge=0.0)
    vision_enabled: bool = True
    vision_max_pages: int = Field(default=5, ge=1)

class ExtractionSettings(BaseModel):
    min_text_coverage_for_rule: float = Field(default=0.8, ge=0.0, le=1.0)
    max_pages_rule_based: int = Field(default=10, ge=1)
    llm_on_extraction_failure: bool = True

class OrgSettings(BaseModel):
    default_currency: str = "EUR"  # ISO 4217
    price_tolerance_percent: float = Field(default=5.0, ge=0.0)
    require_unit_price: bool = False

    matching: MatchingSettings = MatchingSettings()
    customer_detection: CustomerDetectionSettings = CustomerDetectionSettings()
    ai: AISettings = AISettings()
    extraction: ExtractionSettings = ExtractionSettings()
```

### API Endpoints

#### GET `/org/settings`
```json
// Response 200
{
  "default_currency": "EUR",
  "price_tolerance_percent": 5.0,
  "require_unit_price": false,
  "matching": {
    "auto_apply_threshold": 0.92,
    "auto_apply_gap": 0.10
  },
  "customer_detection": {
    "auto_select_threshold": 0.90,
    "require_manual_review_if_multiple": true
  },
  "ai": {
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "llm_budget_daily_usd": 10.0,
    "vision_enabled": true,
    "vision_max_pages": 5
  },
  "extraction": {
    "min_text_coverage_for_rule": 0.8,
    "max_pages_rule_based": 10,
    "llm_on_extraction_failure": true
  }
}
```

#### PATCH `/org/settings`
```json
// Request
{
  "matching": {
    "auto_apply_threshold": 0.95
  },
  "ai": {
    "llm_budget_daily_usd": 20.0
  }
}

// Response 200
{
  "message": "Settings updated successfully",
  "settings": { /* full updated settings */ }
}
```

### Background Job Org_id Handling

```python
# Enqueue job with explicit org_id
@router.post("/documents/{document_id}/extract")
async def trigger_extraction(document_id: UUID, org_id: UUID = Depends(get_org_id)):
    extract_document.delay(
        document_id=str(document_id),
        org_id=str(org_id)  # Explicit parameter
    )
    return {"status": "enqueued"}

# Worker task signature
@celery_app.task
def extract_document(document_id: str, org_id: str):
    org_uuid = UUID(org_id)
    # Validate org exists
    org = session.query(Org).filter(Org.id == org_uuid).first()
    if not org:
        raise ValueError(f"Invalid org_id: {org_id}")

    # All queries use org_uuid
    document = session.query(Document).filter(
        Document.id == UUID(document_id),
        Document.org_id == org_uuid  # Explicit filter
    ).first()
    ...
```

### Database Constraints

Ensure all multi-tenant tables have:

```sql
-- Foreign key constraint
ALTER TABLE document
ADD CONSTRAINT fk_document_org
FOREIGN KEY (org_id) REFERENCES org(id)
ON DELETE RESTRICT;  -- Prevent org deletion with data

-- NOT NULL constraint
ALTER TABLE document
ALTER COLUMN org_id SET NOT NULL;

-- Index for query performance
CREATE INDEX idx_document_org ON document(org_id);
```

### Implementation Note

ExtractionSettings and AISettings enable future features (specs 009-012). For MVP, these settings are stored but not enforced until respective specs are implemented.

### Testing Utilities

```python
# Test fixture for multi-org data isolation
@pytest.fixture
def multi_org_setup(db_session):
    org_a = create_test_org("org-a")
    org_b = create_test_org("org-b")

    # Create identical data for both orgs
    create_test_document(org_a.id, filename="test.pdf")
    create_test_document(org_b.id, filename="test.pdf")

    return org_a, org_b

def test_org_isolation(multi_org_setup, client):
    org_a, org_b = multi_org_setup

    # Login as org_a user
    token_a = login_as_org(client, org_a.slug, "user@orga.com")

    # Query documents
    response = client.get("/documents", headers={"Authorization": f"Bearer {token_a}"})

    # Should only see org_a's documents
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["org_id"] == str(org_a.id)
```

## Out of Scope

- Org creation workflow (assume orgs are created during onboarding, not via API)
- Org deletion / deactivation
- Org slug changes (immutable after creation)
- Super-admin role with cross-org access
- Org hierarchy or parent/child relationships
- Settings inheritance or templates
- Settings change history/audit (basic audit log only)

## Testing Strategy

### Unit Tests
- Settings schema validation (valid/invalid values)
- Settings merge/update logic (partial updates)
- Org_id derivation from JWT
- Default settings generation

### Integration Tests
- Cross-org data isolation (multiple orgs, verify no leakage)
- API calls with different org tokens (cannot access other org's data)
- 404 behavior for cross-org resource access
- Settings CRUD operations
- Settings validation error handling
- Org_id foreign key constraint enforcement
- Background job org_id isolation

### Security Tests
- JWT org_id tampering detection
- SQL injection attempts on org_id filter
- Timing attack resistance (404 timing for same org vs different org)
- Mass assignment prevention (cannot change org_id via API)
- Background job with invalid org_id fails safely

### Performance Tests
- Org_id filter adds minimal query overhead (<5ms)
- Settings retrieval is fast (<50ms)
- Index usage verification (EXPLAIN ANALYZE queries)
