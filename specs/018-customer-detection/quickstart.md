# Quickstart: Customer Detection Development

**Feature**: Customer Detection (Multi-Signal Detection & Disambiguation)
**Date**: 2025-12-27

## Prerequisites

- Python 3.12+
- PostgreSQL 16 with `pg_trgm` extension
- Docker (for local PostgreSQL)
- Git

## Local Development Setup

### 1. Database Setup

```bash
# Start PostgreSQL with Docker
docker run -d \
  --name orderflow-postgres \
  -e POSTGRES_DB=orderflow_dev \
  -e POSTGRES_USER=orderflow \
  -e POSTGRES_PASSWORD=dev_password \
  -p 5432:5432 \
  postgres:16

# Wait for PostgreSQL to be ready
sleep 5

# Enable pg_trgm extension
docker exec orderflow-postgres psql -U orderflow -d orderflow_dev -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

### 2. Run Migrations

```bash
# From backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head
```

### 3. Load Test Data

```bash
# Load test fixtures (customers, contacts, products)
python scripts/load_fixtures.py --fixture customer_detection

# This creates:
# - 5 test customers with different contact patterns
# - 10 customer contacts with various email domains
# - Sample inbound messages with different signal patterns
```

### 4. Run Tests

```bash
# Unit tests for signal extraction
pytest tests/unit/customer_detection/test_signal_extraction.py -v

# Unit tests for aggregation formula
pytest tests/unit/customer_detection/test_aggregation.py -v

# Integration tests (requires database)
pytest tests/integration/customer_detection/ -v

# Run all customer detection tests
pytest tests/ -k customer_detection -v
```

### 5. Manual Testing via API

```bash
# Start FastAPI development server
uvicorn src.main:app --reload --port 8000

# In another terminal, test customer detection
curl -X POST http://localhost:8000/api/v1/draft-orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "inbound_message_id": "uuid-of-inbound-message",
    "document_id": "uuid-of-document"
  }'

# Check detection results
curl http://localhost:8000/api/v1/draft-orders/<draft-id> \
  -H "Authorization: Bearer <token>" \
  | jq '.customer_candidates_json'
```

## Test Fixtures

### Fixture Scenario: Email Exact Match (S1)

**Setup**:
```python
# Customer: "Acme Corp"
customer = Customer(
    org_id=org_id,
    name="Acme Corp",
    erp_customer_number="CUST-001"
)

# Contact: buyer@acme.com
contact = CustomerContact(
    customer_id=customer.id,
    email="buyer@acme.com",
    name="John Buyer"
)

# Inbound message from buyer@acme.com
inbound = InboundMessage(
    org_id=org_id,
    from_email="buyer@acme.com",
    subject="Order PO-12345"
)
```

**Expected Result**:
- 1 candidate: Acme Corp, score=0.95, signals={"from_email_exact": True}
- Auto-selected (score ≥ 0.90, gap N/A for single candidate)

### Fixture Scenario: Domain Match + Doc Number (S2 + S4)

**Setup**:
```python
# Customer: "Beta GmbH"
customer = Customer(
    org_id=org_id,
    name="Beta GmbH",
    erp_customer_number="4711"
)

# Contact: orders@beta.com
contact = CustomerContact(
    customer_id=customer.id,
    email="orders@beta.com"
)

# Inbound message from new-buyer@beta.com (not exact match)
inbound = InboundMessage(
    org_id=org_id,
    from_email="new-buyer@beta.com"
)

# Document contains "Kundennr: 4711"
document = Document(
    extracted_text="Invoice\n\nKundennr: 4711\n\nOrder Details..."
)
```

**Expected Result**:
- 1 candidate: Beta GmbH
- Signals: S2 (domain match) = 0.75, S4 (doc number) = 0.98
- Combined score: 1 - (1-0.75)*(1-0.98) = 1 - 0.25*0.02 = 0.995
- Auto-selected (score ≥ 0.90)

### Fixture Scenario: Ambiguous (Multiple Candidates)

**Setup**:
```python
# Customer 1: "Gamma Inc"
customer1 = Customer(name="Gamma Inc", erp_customer_number="CUST-003")
contact1 = CustomerContact(customer_id=customer1.id, email="orders@gamma.com")

# Customer 2: "Gamma North"
customer2 = Customer(name="Gamma North", erp_customer_number="CUST-004")
contact2 = CustomerContact(customer_id=customer2.id, email="north@gamma.com")

# Customer 3: "Gamma South"
customer3 = Customer(name="Gamma South", erp_customer_number="CUST-005")
contact3 = CustomerContact(customer_id=customer3.id, email="south@gamma.com")

# Inbound message from generic domain
inbound = InboundMessage(from_email="supplier@gmail.com")

# Document contains "Gamma" (fuzzy matches all three)
document = Document(extracted_text="Order from Gamma")
```

**Expected Result**:
- 3 candidates: Gamma Inc (0.70), Gamma North (0.68), Gamma South (0.68)
- Top1-Top2 gap = 0.02 (< 0.07 min_gap)
- Ambiguous: customer_id=NULL, CUSTOMER_AMBIGUOUS issue created

## Key Test Scenarios

### Unit Test: Signal Extraction

```python
def test_extract_from_email_exact():
    extractor = SignalExtractor()
    inbound = InboundMessage(from_email="buyer@acme.com")
    contacts = [CustomerContact(email="buyer@acme.com", customer_id=UUID("..."))]

    candidates = extractor.extract_from_email(inbound, contacts)

    assert len(candidates) == 1
    assert candidates[0].score == 0.95
    assert candidates[0].signals == {"from_email_exact": True}

def test_extract_doc_customer_number():
    extractor = SignalExtractor()
    doc_text = "Invoice\n\nKundennr: 4711\n\nTotal: €100"
    customers = [Customer(erp_customer_number="4711", id=UUID("..."))]

    candidates = extractor.extract_doc_customer_number(doc_text, customers)

    assert len(candidates) == 1
    assert candidates[0].score == 0.98
    assert candidates[0].signals["doc_erp_number"] == "4711"

def test_fuzzy_name_match():
    extractor = SignalExtractor()
    doc_text = "Order from Muster GmbH"
    # Mock database query result
    fuzzy_results = [
        (Customer(name="Muster GmbH & Co. KG", id=UUID("...")), 0.85)
    ]

    candidates = extractor.extract_doc_company_name_fuzzy(doc_text, fuzzy_results)

    assert len(candidates) == 1
    # score = 0.40 + 0.60 * 0.85 = 0.91 (clamped to 0.85)
    assert candidates[0].score == 0.85
```

### Integration Test: End-to-End Detection

```python
def test_customer_detection_auto_select(db_session, test_org, test_customer):
    # Setup
    contact = CustomerContact(
        customer_id=test_customer.id,
        email="buyer@test.com"
    )
    db_session.add(contact)

    inbound = InboundMessage(
        org_id=test_org.id,
        from_email="buyer@test.com",
        subject="Order"
    )
    db_session.add(inbound)
    db_session.commit()

    draft = DraftOrder(org_id=test_org.id, inbound_message_id=inbound.id)
    db_session.add(draft)
    db_session.commit()

    # Execute
    service = CustomerDetectionService(db_session)
    result = service.detect_customer(draft)

    # Assert
    assert result.selected_customer_id == test_customer.id
    assert result.confidence == 0.95
    assert result.auto_selected is True

    # Verify database state
    db_session.refresh(draft)
    assert draft.customer_id == test_customer.id
    assert draft.customer_confidence == 0.95

    candidates = db_session.query(CustomerDetectionCandidate).filter_by(
        draft_order_id=draft.id
    ).all()
    assert len(candidates) == 1
    assert candidates[0].status == "SELECTED"
```

## Debugging Tips

### Check Signal Extraction

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run detection with debug output
pytest tests/integration/customer_detection/test_detection_flow.py::test_signal_extraction -v -s
```

**Expected Output**:
```
DEBUG customer_detection.service: Extracting signals for draft_order_id=uuid
DEBUG customer_detection.service: S1 from_email_exact: 1 candidates
DEBUG customer_detection.service: S2 from_domain: 2 candidates
DEBUG customer_detection.service: S4 doc_customer_number: 1 candidate
DEBUG customer_detection.service: Aggregating 4 candidates for 2 unique customers
DEBUG customer_detection.service: Customer uuid-1: score=0.995 (signals: S2, S4)
DEBUG customer_detection.service: Customer uuid-2: score=0.75 (signals: S2)
DEBUG customer_detection.service: Auto-select: top1=0.995, top2=0.75, gap=0.245 → AUTO_SELECTED
```

### Inspect Candidate JSON

```sql
-- View candidates for a draft
SELECT
    c.name AS customer_name,
    cdc.score,
    cdc.signals_json,
    cdc.status
FROM customer_detection_candidate cdc
JOIN customer c ON c.id = cdc.customer_id
WHERE cdc.draft_order_id = '<draft-uuid>'
ORDER BY cdc.score DESC;

-- View customer_candidates_json (UI payload)
SELECT customer_candidates_json
FROM draft_order
WHERE id = '<draft-uuid>';
```

### Test Fuzzy Name Matching

```sql
-- Test trigram similarity
SELECT
    name,
    similarity(name, 'Muster GmbH') AS sim
FROM customer
WHERE org_id = '<org-uuid>'
  AND similarity(name, 'Muster GmbH') > 0.40
ORDER BY sim DESC
LIMIT 5;
```

**Expected Output**:
```
         name          | sim
-----------------------+------
 Muster GmbH           | 1.00
 Muster GmbH & Co. KG  | 0.85
 Muster Industries     | 0.52
```

## Performance Profiling

### Benchmark Detection Speed

```python
import time
from src.domain.customer_detection.service import CustomerDetectionService

def benchmark_detection(db_session, num_drafts=100):
    service = CustomerDetectionService(db_session)
    drafts = create_test_drafts(num_drafts)

    start = time.time()
    for draft in drafts:
        service.detect_customer(draft)
    elapsed = time.time() - start

    print(f"Processed {num_drafts} drafts in {elapsed:.2f}s")
    print(f"Average: {(elapsed / num_drafts * 1000):.2f}ms per draft")

# Target: <100ms per draft
```

### Profile Fuzzy Name Search

```python
def profile_fuzzy_search(db_session, query="Muster GmbH"):
    from sqlalchemy import text

    # Warm up
    db_session.execute(text("SELECT similarity(name, :q) FROM customer WHERE org_id = :org LIMIT 1"), {"q": query, "org": org_id})

    start = time.time()
    result = db_session.execute(
        text("""
            SELECT id, name, similarity(name, :query) AS sim
            FROM customer
            WHERE org_id = :org_id
              AND similarity(name, :query) > 0.40
            ORDER BY sim DESC
            LIMIT 5
        """),
        {"query": query, "org_id": org_id}
    ).fetchall()
    elapsed = (time.time() - start) * 1000

    print(f"Fuzzy search: {elapsed:.2f}ms for {len(result)} results")
    # Target: <50ms
```

## Common Issues

### Issue: No Candidates Generated

**Symptom**: `draft_order.customer_candidates_json` is empty, no candidates in table.

**Possible Causes**:
1. No customer_contacts exist for org
2. Inbound message has `from_email=NULL`
3. Document text is empty (no doc signals)
4. All similarity scores below thresholds (fuzzy match < 0.40)

**Debug**:
```python
# Check contact count
contact_count = db.session.query(CustomerContact).filter_by(org_id=org_id).count()
print(f"Contacts: {contact_count}")

# Check inbound message
inbound = db.session.query(InboundMessage).filter_by(id=inbound_id).first()
print(f"From: {inbound.from_email}")

# Check document text
doc = db.session.query(Document).filter_by(id=document_id).first()
print(f"Text length: {len(doc.extracted_text)}")
```

### Issue: Always Ambiguous

**Symptom**: Even with exact email match, CUSTOMER_AMBIGUOUS issue is created.

**Possible Causes**:
1. Multiple customers share same contact email (data error)
2. `auto_select_threshold` is set too high (> 0.95)
3. `min_gap` is set too high (> 0.10)

**Debug**:
```sql
-- Check for duplicate contact emails
SELECT email, COUNT(DISTINCT customer_id)
FROM customer_contact
WHERE org_id = '<org-uuid>'
GROUP BY email
HAVING COUNT(DISTINCT customer_id) > 1;

-- Check org settings
SELECT settings_json->'customer_detection'
FROM organization
WHERE id = '<org-uuid>';
```

### Issue: Wrong Customer Auto-Selected

**Symptom**: Auto-selection chooses wrong customer, operator must override.

**Analysis**:
1. Check signal weights in detection log
2. Review signals_json for selected candidate
3. Compare with expected customer signals
4. Log feedback event for later analysis

**Fix**:
- Adjust signal scores in code (e.g., lower S2 for generic domains)
- Add customer-specific rules (e.g., skip S2 if domain is gmail.com)
- Increase `min_gap` to require stronger separation

## Next Steps

After local testing:
1. Deploy to staging environment
2. Import production customer/contact data
3. Run detection on sample inbound messages
4. Measure auto-selection accuracy (target: ≥97%)
5. Monitor ambiguity rate (target: <15%)
6. Collect feedback events for 1 week
7. Analyze feedback to tune signal weights

**Success Criteria**: Auto-selection works for ≥90% of orders with ≤3% manual override rate.
