# Multi-Tenant Isolation Guide

**Version:** 1.0
**Last Updated:** 2026-01-04
**SSOT Reference:** §5.1, §10.1, §11.2

## Overview

OrderFlow implements strict multi-tenant isolation to prevent data leakage between organizations. Every database query is automatically scoped by `org_id`, ensuring users can only access data within their organization.

This document explains:
1. How tenant isolation works
2. Patterns for API endpoints
3. Patterns for background jobs
4. Testing strategies
5. Common pitfalls and how to avoid them

## Core Concepts

### 1. Organization (Tenant)

Every organization in OrderFlow is a **tenant** with completely isolated data:

- Each org has a unique UUID (`org.id`)
- All multi-tenant tables have `org_id UUID NOT NULL` foreign key
- Users belong to exactly one organization
- JWT tokens contain `org_id` claim for automatic scoping

### 2. Automatic Tenant Scoping

The system enforces tenant isolation at multiple layers:

**Layer 1: JWT Token**
- User authenticates → receives JWT with `org_id` claim
- `org_id` derived from user's organization (server-side, tamper-proof)
- Cannot be modified by client

**Layer 2: API Dependencies**
- All endpoints use `get_org_id()` dependency
- Extracts `org_id` from validated JWT token
- Provides tenant context to endpoint handlers

**Layer 3: Database Queries**
- All queries MUST filter by `org_id`
- Use `TenantQuery.get_or_404()` for single records
- Use `TenantQuery.scoped_query()` for lists

**Layer 4: Background Jobs**
- All Celery tasks receive `org_id` as explicit parameter
- Use `validate_org_id()` to verify organization exists
- Use `get_scoped_session()` for database access

### 3. 404 Not 403

When a user attempts to access a resource from another organization:

**WRONG:**
```python
# Returns 403 Forbidden
if record.org_id != user.org_id:
    raise HTTPException(403, "Access denied")
```

**RIGHT:**
```python
# Returns 404 Not Found (same as non-existent resource)
record = db.query(Model).filter(
    Model.id == record_id,
    Model.org_id == org_id  # Scoped query
).first()

if not record:
    raise HTTPException(404, f"{Model.__name__} not found")
```

**Why:** Returning 403 reveals that the resource exists in another org. This enables enumeration attacks. Always return 404 to prevent information leakage.

## API Endpoint Patterns

### Pattern 1: List Endpoint

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..dependencies import get_org_id
from ..auth.dependencies import get_current_user
from ..models import Document

router = APIRouter()

@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id),
    current_user = Depends(get_current_user)
):
    """List all documents for current organization."""
    documents = db.query(Document).filter(
        Document.org_id == org_id  # REQUIRED
    ).all()

    return {"items": documents}
```

**Key Points:**
- Use `get_org_id()` dependency to extract org_id from JWT
- ALWAYS filter queries by `org_id`
- org_id comes from JWT, never from request body/query params

### Pattern 2: Get Single Record

```python
from ..dependencies import TenantQuery

@router.get("/documents/{document_id}")
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    """Get single document (404 if not found or wrong org)."""
    # Use TenantQuery helper for automatic 404 on wrong org
    document = TenantQuery.get_or_404(db, Document, document_id, org_id)

    return document
```

**Key Points:**
- Use `TenantQuery.get_or_404()` for automatic isolation
- Returns 404 for both non-existent and cross-org resources
- Single query, no need for manual permission checking

### Pattern 3: Create Record

```python
@router.post("/documents")
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    """Create new document in current organization."""
    document = Document(
        **data.model_dump(),
        org_id=org_id  # REQUIRED - auto-populate from JWT
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document
```

**Key Points:**
- ALWAYS set `org_id` on new records
- Use `org_id` from dependency (JWT token), not request body
- Database foreign key constraint prevents invalid org_id

### Pattern 4: Update Record

```python
@router.patch("/documents/{document_id}")
def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    """Update document (404 if not found or wrong org)."""
    # Fetch with org_id scoping
    document = TenantQuery.get_or_404(db, Document, document_id, org_id)

    # Update fields
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(document, key, value)

    db.commit()
    db.refresh(document)

    return document
```

**Key Points:**
- Use scoped fetch (prevents updating other org's data)
- NEVER allow org_id to be changed via API
- org_id is immutable after creation

### Pattern 5: Delete Record

```python
@router.delete("/documents/{document_id}")
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    """Delete document (404 if not found or wrong org)."""
    document = TenantQuery.get_or_404(db, Document, document_id, org_id)

    db.delete(document)
    db.commit()

    return {"message": "Document deleted"}
```

**Key Points:**
- Scoped fetch prevents deleting other org's data
- Returns 404 if document doesn't exist or belongs to another org

## Background Job Patterns

### Pattern 1: Task Definition

```python
from celery import shared_task
from uuid import UUID
from backend.src.workers import validate_org_id, get_scoped_session
from backend.src.models import Document

@shared_task
def process_document(document_id: str, org_id: str):
    """Process document for specific organization.

    Args:
        document_id: Document UUID (string for JSON serialization)
        org_id: Organization UUID (string, REQUIRED)

    Returns:
        Dict with processing result
    """
    # 1. Validate org_id
    org_uuid = validate_org_id(org_id)

    # 2. Get scoped session
    session = get_scoped_session(org_uuid)

    try:
        # 3. Query with EXPLICIT org_id filter
        document = session.query(Document).filter(
            Document.id == UUID(document_id),
            Document.org_id == org_uuid  # REQUIRED
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found in org {org_id}")

        # 4. Process document
        result = perform_processing(document)

        # 5. Commit
        session.commit()

        return {"status": "success", "result": result}

    finally:
        session.close()
```

**Key Points:**
- ALWAYS validate org_id at start of task
- Use `get_scoped_session()` for database access
- ALWAYS filter queries by org_id (never assume session handles it)
- Handle org_id as string (JSON serializable for Celery)

### Pattern 2: Enqueueing Task

```python
@router.post("/documents/{document_id}/process")
def trigger_processing(
    document_id: UUID,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    """Trigger background processing for document."""
    # Verify document exists and belongs to org
    document = TenantQuery.get_or_404(db, Document, document_id, org_id)

    # Enqueue task with explicit org_id
    process_document.delay(
        document_id=str(document_id),
        org_id=str(org_id)  # REQUIRED - from JWT, not request body
    )

    return {"status": "enqueued"}
```

**Key Points:**
- Extract org_id from JWT token (via `get_org_id()`)
- Pass org_id explicitly to task.delay()
- NEVER derive org_id from global state in workers
- Convert UUIDs to strings for JSON serialization

## Organization Settings

### Retrieving Settings

```python
from backend.src.tenancy import OrgSettings

@router.get("/some-endpoint")
def my_endpoint(
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)
):
    # Fetch organization
    org = db.query(Org).filter(Org.id == org_id).first()

    # Parse settings with defaults
    settings = OrgSettings(**org.settings_json)

    # Use settings
    if settings.matching.auto_apply_threshold > 0.95:
        # High confidence matching
        ...
```

**Key Points:**
- Settings stored as JSONB in `org.settings_json`
- Parse with `OrgSettings` Pydantic model for validation
- Empty `{}` is valid - Pydantic applies defaults

### Updating Settings (ADMIN only)

Settings management is handled by `/org/settings` endpoints:

```bash
# Get current settings
GET /org/settings
Authorization: Bearer <token>

# Update settings (ADMIN only)
PATCH /org/settings
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "default_currency": "CHF",
  "matching": {
    "auto_apply_threshold": 0.95
  }
}
```

Partial updates are deep-merged with existing settings. See `backend/src/tenancy/router.py` for implementation.

## Testing Strategies

### 1. Multi-Org Fixtures

Use test fixtures from `backend/tests/fixtures/multi_org.py`:

```python
def test_cross_org_isolation(multi_org_setup, client):
    org_a, org_b, user_a, user_b = multi_org_setup

    # Create document in org A
    doc_a = create_document(org_a.id, "doc-a.pdf")

    # Login as org B user
    headers = get_auth_headers(user_b)

    # Try to access org A's document
    response = client.get(f"/documents/{doc_a.id}", headers=headers)

    # Should get 404 (not 403)
    assert response.status_code == 404
```

### 2. SQL Query Logging

Enable SQL logging to verify org_id filters are present:

```python
# In database.py
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Log all SQL queries
)
```

Then check logs for queries like:
```sql
SELECT * FROM document WHERE document.id = ? AND document.org_id = ?
```

Every multi-tenant query should include `AND table.org_id = ?`.

### 3. Table Convention Tests

Verify all multi-tenant tables have proper constraints:

```python
def test_table_has_org_id_constraint(db_session):
    """Verify all multi-tenant tables have org_id NOT NULL constraint."""
    from sqlalchemy import inspect

    inspector = inspect(db_session.bind)

    multi_tenant_tables = [
        "document", "draft_order", "draft_order_line",
        "inbound_message", "sku_mapping", "product", "customer"
    ]

    for table_name in multi_tenant_tables:
        columns = inspector.get_columns(table_name)
        org_id_col = next((c for c in columns if c["name"] == "org_id"), None)

        assert org_id_col is not None, f"Table {table_name} missing org_id column"
        assert not org_id_col["nullable"], f"Table {table_name} org_id allows NULL"
```

## Common Pitfalls

### Pitfall 1: Forgetting org_id Filter

**WRONG:**
```python
# DANGER: Returns data from ALL orgs
documents = db.query(Document).all()
```

**RIGHT:**
```python
documents = db.query(Document).filter(Document.org_id == org_id).all()
```

### Pitfall 2: Using Request Body for org_id

**WRONG:**
```python
@router.post("/documents")
def create_document(data: DocumentCreate, db: Session = Depends(get_db)):
    # DANGER: Client controls org_id
    document = Document(**data.model_dump())  # data.org_id from request
```

**RIGHT:**
```python
@router.post("/documents")
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    org_id: UUID = Depends(get_org_id)  # From JWT
):
    document = Document(
        **data.model_dump(exclude={"org_id"}),  # Exclude if in schema
        org_id=org_id  # From JWT token
    )
```

### Pitfall 3: Returning 403 Instead of 404

**WRONG:**
```python
if document.org_id != user.org_id:
    raise HTTPException(403, "Access denied")  # Leaks existence
```

**RIGHT:**
```python
# Query with org_id filter - returns None if wrong org
document = db.query(Document).filter(
    Document.id == document_id,
    Document.org_id == org_id
).first()

if not document:
    raise HTTPException(404, "Document not found")  # Same for both cases
```

### Pitfall 4: Missing org_id in Background Jobs

**WRONG:**
```python
@shared_task
def process_document(document_id: str):
    # DANGER: No org_id - how to scope query?
    session = SessionLocal()
    document = session.query(Document).filter(Document.id == UUID(document_id)).first()
```

**RIGHT:**
```python
@shared_task
def process_document(document_id: str, org_id: str):
    org_uuid = validate_org_id(org_id)
    session = get_scoped_session(org_uuid)
    document = session.query(Document).filter(
        Document.id == UUID(document_id),
        Document.org_id == org_uuid
    ).first()
```

### Pitfall 5: Modifying org_id After Creation

**WRONG:**
```python
@router.patch("/documents/{document_id}")
def update_document(document_id: UUID, data: DocumentUpdate, ...):
    document.org_id = data.org_id  # DANGER: Can move record to another org
```

**RIGHT:**
```python
# org_id is immutable - exclude from update schema
class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    # org_id NOT INCLUDED - cannot be changed

@router.patch("/documents/{document_id}")
def update_document(document_id: UUID, data: DocumentUpdate, ...):
    # Only update allowed fields
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(document, key, value)
```

## Quick Reference

### Must-Have Checklist for New Endpoints

- [ ] Use `get_org_id()` dependency to extract org_id
- [ ] Filter ALL queries by `org_id`
- [ ] Use `TenantQuery.get_or_404()` for single records
- [ ] Return 404 (not 403) for cross-org access
- [ ] Set `org_id` on new records (from JWT, not request)
- [ ] NEVER allow org_id to be modified via API
- [ ] Add integration test with multi-org fixtures

### Must-Have Checklist for Background Jobs

- [ ] Accept `org_id: str` as task parameter
- [ ] Call `validate_org_id(org_id)` at start
- [ ] Use `get_scoped_session(org_uuid)` for database
- [ ] Filter ALL queries by `org_id`
- [ ] Pass org_id when enqueueing (from JWT token)
- [ ] Handle org_id as string (UUID.str for Celery)
- [ ] Add test with multiple orgs

## Support

For questions or issues:
- Review spec: `specs/003-tenancy-isolation/spec.md`
- Check examples: `backend/src/tenancy/router.py`
- Review tests: `backend/tests/fixtures/multi_org.py`
- SSOT reference: `SSOT_SPEC.md` §5.1, §10.1, §11.2
