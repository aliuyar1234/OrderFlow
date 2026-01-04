# Quickstart: Validation Engine Development

**Feature**: Validation Engine
**Date**: 2025-12-27

## Setup

```bash
# Database with test data
docker run -d --name orderflow-postgres -p 5432:5432 postgres:16
cd backend && pip install -r requirements.txt
alembic upgrade head
python scripts/load_fixtures.py --fixture validation

# Run tests
pytest tests/unit/validation/ -v        # Rule tests
pytest tests/integration/validation/ -v  # End-to-end tests
```

## Test Scenarios

### Test: Product Validation
```python
def test_unknown_product():
    draft = DraftOrder(lines=[DraftOrderLine(internal_sku="UNKNOWN-123")])
    engine = ValidationEngine()
    issues = engine.validate(draft)

    assert len(issues) == 1
    assert issues[0].type == "UNKNOWN_PRODUCT"
    assert issues[0].severity == ValidationIssueSeverity.ERROR
```

### Test: Price Validation
```python
def test_price_mismatch():
    # Customer price: €10.00, tolerance: 5%
    customer_price = CustomerPrice(unit_price=10.00)
    line = DraftOrderLine(unit_price=12.00)  # 20% over

    engine = ValidationEngine()
    issues = engine.validate_price(line, customer_price, tolerance=0.05)

    assert len(issues) == 1
    assert issues[0].type == "PRICE_MISMATCH"
    assert issues[0].severity == ValidationIssueSeverity.WARNING
```

### Test: Ready-Check
```python
def test_ready_check_blocks_on_error():
    issues = [
        ValidationIssue(type="UNKNOWN_PRODUCT", severity=ERROR, status=OPEN),
        ValidationIssue(type="PRICE_MISMATCH", severity=WARNING, status=OPEN)
    ]

    result = compute_ready_check(issues)

    assert result.is_ready is False
    assert "UNKNOWN_PRODUCT" in result.blocking_reasons
    assert "PRICE_MISMATCH" not in result.blocking_reasons  # Warnings don't block
```

## Debugging

```sql
-- View issues for a draft
SELECT type, severity, status, message
FROM validation_issue
WHERE draft_order_id = '<uuid>'
ORDER BY severity DESC, created_at;

-- Check ready status
SELECT ready_check_json
FROM draft_order
WHERE id = '<uuid>';
```
