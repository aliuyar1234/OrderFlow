# Research: Tenancy Isolation

**Feature**: 003-tenancy-isolation
**Date**: 2025-12-27

## Key Decisions

### 1. SQLAlchemy Session-Scoped org_id

**Decision**: Store org_id in SQLAlchemy session.info and auto-inject into queries.

**Pattern**:
```python
def get_scoped_session(org_id: UUID) -> Session:
    session = SessionLocal()
    session.info["org_id"] = org_id
    return session

def scoped_query(session: Session, model):
    org_id = session.info.get("org_id")
    if not org_id:
        raise ValueError("org_id not set in session")
    return session.query(model).filter(model.org_id == org_id)
```

**Rationale**: Prevents accidental cross-org queries by centralizing org_id logic.

**References**: SSOT §5.1, §11.2

---

### 2. 404 (Not 403) for Cross-Org Access

**Decision**: Return 404 when resource exists but belongs to different org.

**Rationale**:
- Prevents enumeration attacks (attacker can't discover resource IDs)
- Consistent with "resource doesn't exist from your perspective"
- OWASP recommendation for multi-tenant systems

**Implementation**:
```python
resource = scoped_query(session, Model).filter(Model.id == resource_id).first()
if not resource:
    raise HTTPException(status_code=404, detail="Resource not found")
# Never: if resource.org_id != current_org_id: raise 403
```

**References**: SSOT §11.3 (ID guessing prevention)

---

### 3. Org Settings Validation with Pydantic

**Decision**: Validate settings_json against OrgSettings schema before saving.

**Schema** (from SSOT §10.1):
```python
class OrgSettings(BaseModel):
    default_currency: str = "EUR"
    price_tolerance_percent: float = 5.0
    require_unit_price: bool = False
    matching: MatchingSettings = MatchingSettings()
    customer_detection: CustomerDetectionSettings = CustomerDetectionSettings()
    ai: AISettings = AISettings()
    extraction: ExtractionSettings = ExtractionSettings()
```

**Benefits**:
- Type safety despite JSONB storage
- Default value management
- Range validation (e.g., 0.0 <= threshold <= 1.0)
- API documentation auto-generated from schema

---

### 4. Explicit org_id in Background Jobs

**Decision**: Pass org_id as explicit parameter to Celery tasks.

**Pattern**:
```python
@celery_app.task
def extract_document(document_id: str, org_id: str):
    org_uuid = UUID(org_id)
    session = get_scoped_session(org_uuid)
    # All queries use scoped session
```

**Rationale**: Prevents "current org" race conditions in async processing.

**References**: Constitution Principle III (Multi-Tenant Isolation)

---

## Testing Strategy

### Multi-Org Isolation Tests

```python
@pytest.fixture
def multi_org_fixture(db_session):
    org_a = create_test_org("org-a")
    org_b = create_test_org("org-b")
    create_test_data(org_a.id, name="Shared Name")
    create_test_data(org_b.id, name="Shared Name")
    return org_a, org_b

def test_org_isolation(multi_org_fixture, client):
    org_a, org_b = multi_org_fixture
    token_a = login_as_org(client, org_a.slug)

    response = client.get("/resources", headers={"Authorization": f"Bearer {token_a}"})
    resources = response.json()["items"]

    # Should only see org_a's resources
    assert all(r["org_id"] == str(org_a.id) for r in resources)
```

---

## References

- SSOT §5.1: Multi-tenant conventions
- SSOT §10.1: Org settings schema
- SSOT §11.2: Tenant isolation
- Constitution Principle III
