# Tenancy Isolation Quick Reference

**One-page guide for OrderFlow multi-tenant development**

## Import Statements

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from backend.src.database import get_db
from backend.src.dependencies import get_org_id, TenantQuery
from backend.src.auth.dependencies import get_current_user, require_role
from backend.src.auth.roles import UserRole
from backend.src.tenancy import OrgSettings
from backend.src.workers import validate_org_id, get_scoped_session
```

## API Endpoint Patterns

### List All (Scoped)
```python
@router.get("/resources")
def list_resources(
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    return db.query(Resource).filter(Resource.org_id == org_id).all()
```

### Get One (404 if wrong org)
```python
@router.get("/resources/{id}")
def get_resource(
    id: UUID,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    return TenantQuery.get_or_404(db, Resource, id, org_id)
```

### Create (Auto org_id)
```python
@router.post("/resources")
def create_resource(
    data: ResourceCreate,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    resource = Resource(**data.model_dump(), org_id=org_id)
    db.add(resource)
    db.commit()
    return resource
```

### Update (Scoped)
```python
@router.patch("/resources/{id}")
def update_resource(
    id: UUID,
    data: ResourceUpdate,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    resource = TenantQuery.get_or_404(db, Resource, id, org_id)
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(resource, key, value)
    db.commit()
    return resource
```

### Delete (Scoped)
```python
@router.delete("/resources/{id}")
def delete_resource(
    id: UUID,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    resource = TenantQuery.get_or_404(db, Resource, id, org_id)
    db.delete(resource)
    db.commit()
    return {"message": "Deleted"}
```

## Background Job Patterns

### Task Definition
```python
from celery import shared_task
from backend.src.workers import validate_org_id, get_scoped_session

@shared_task
def process_resource(resource_id: str, org_id: str):
    org_uuid = validate_org_id(org_id)
    session = get_scoped_session(org_uuid)
    try:
        resource = session.query(Resource).filter(
            Resource.id == UUID(resource_id),
            Resource.org_id == org_uuid
        ).first()
        # ... process ...
        session.commit()
    finally:
        session.close()
```

### Enqueueing Task
```python
@router.post("/resources/{id}/process")
def trigger_processing(
    id: UUID,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    process_resource.delay(
        resource_id=str(id),
        org_id=str(org_id)  # From JWT, not request
    )
    return {"status": "enqueued"}
```

## Common Mistakes

### ❌ WRONG: No org_id filter
```python
db.query(Resource).all()  # Returns ALL orgs' data!
```

### ✅ RIGHT: Always filter
```python
db.query(Resource).filter(Resource.org_id == org_id).all()
```

---

### ❌ WRONG: org_id from request
```python
@router.post("/resources")
def create(data: ResourceCreate):
    Resource(**data.model_dump())  # Client controls org_id!
```

### ✅ RIGHT: org_id from JWT
```python
@router.post("/resources")
def create(data: ResourceCreate, org_id: UUID = Depends(get_org_id)):
    Resource(**data.model_dump(), org_id=org_id)  # Server-side
```

---

### ❌ WRONG: Return 403 for cross-org
```python
if resource.org_id != org_id:
    raise HTTPException(403, "Forbidden")  # Leaks existence
```

### ✅ RIGHT: Return 404
```python
resource = db.query(Resource).filter(
    Resource.id == id,
    Resource.org_id == org_id  # 404 if wrong org
).first()
if not resource:
    raise HTTPException(404, "Not found")
```

---

### ❌ WRONG: Missing org_id in task
```python
@shared_task
def process(resource_id: str):  # No org_id!
    session = SessionLocal()
    # How to filter???
```

### ✅ RIGHT: Explicit org_id
```python
@shared_task
def process(resource_id: str, org_id: str):  # Required!
    org_uuid = validate_org_id(org_id)
    session = get_scoped_session(org_uuid)
```

## Org Settings Usage

### Get Settings
```python
from backend.src.tenancy import OrgSettings

org = db.query(Org).filter(Org.id == org_id).first()
settings = OrgSettings(**org.settings_json)

# Use settings
threshold = settings.matching.auto_apply_threshold
currency = settings.default_currency
```

### API Endpoints
```bash
# Get
GET /org/settings

# Update (ADMIN only)
PATCH /org/settings
{
  "default_currency": "CHF",
  "matching": {"auto_apply_threshold": 0.95}
}
```

## Testing

### Multi-Org Fixture
```python
def test_isolation(multi_org_setup, client):
    org_a, org_b, user_a, user_b = multi_org_setup

    # Create data for org A
    create_resource(org_a.id, "test")

    # Try to access as org B
    headers = get_auth_headers(user_b)
    response = client.get("/resources", headers=headers)

    # Should not see org A's data
    assert len(response.json()) == 0
```

### Auth Headers
```python
from backend.tests.fixtures.multi_org import get_auth_headers

headers = get_auth_headers(user)
response = client.get("/resources", headers=headers)
```

## Checklists

### New Endpoint
- [ ] Use `get_org_id()` dependency
- [ ] Filter ALL queries by org_id
- [ ] Use `TenantQuery.get_or_404()` for single records
- [ ] Return 404 (not 403) for cross-org
- [ ] Set org_id on new records (from JWT)
- [ ] Never allow org_id modification

### New Background Job
- [ ] Accept `org_id: str` parameter
- [ ] Call `validate_org_id(org_id)` at start
- [ ] Use `get_scoped_session(org_uuid)`
- [ ] Filter ALL queries by org_id
- [ ] Pass org_id when enqueueing (from JWT)

### New Table Migration
- [ ] Add `org_id UUID NOT NULL`
- [ ] Add `FOREIGN KEY (org_id) REFERENCES org(id)`
- [ ] Add `CREATE INDEX idx_<table>_org_id ON <table>(org_id)`
- [ ] Add to `MULTI_TENANT_TABLES` in test_table_conventions.py

## Full Documentation

See `docs/tenancy.md` for complete guide with examples.
