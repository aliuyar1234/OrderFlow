# Quickstart: Customer Prices Development

**Date**: 2025-12-27

## Setup

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/load_fixtures.py --fixture customer_prices
```

## Test CSV Import

```bash
# Create test CSV
cat > test_prices.csv <<EOF
erp_customer_number,internal_sku,currency,uom,unit_price,min_qty
CUST-001,SKU-ABC,EUR,PCE,10.00,1
CUST-001,SKU-ABC,EUR,PCE,9.00,100
CUST-001,SKU-ABC,EUR,PCE,8.00,500
EOF

# Import via API
curl -X POST http://localhost:8000/api/v1/imports/customer-prices \
  -H "Authorization: Bearer <token>" \
  -F "file=@test_prices.csv"
```

## Test Tier Selection

```python
def test_tier_selection():
    # Setup: 3 tiers
    prices = [
        CustomerPrice(min_qty=1, unit_price=10.00),
        CustomerPrice(min_qty=100, unit_price=9.00),
        CustomerPrice(min_qty=500, unit_price=8.00),
    ]

    # Test qty=150 → should select tier 2 (min_qty=100)
    selected = select_price_tier(prices, qty=150)
    assert selected.min_qty == 100
    assert selected.unit_price == 9.00
```

## Test Price Validation

```python
def test_price_mismatch():
    expected = CustomerPrice(unit_price=10.00)
    line = DraftOrderLine(unit_price=10.60)  # 6% over
    tolerance = 0.05  # 5%

    mismatch_pct = abs(10.60 - 10.00) / 10.00 * 100  # 6%
    assert mismatch_pct > tolerance  # Should create WARNING
```

## Debugging

```sql
-- View prices for a customer+SKU
SELECT min_qty, unit_price, valid_from, valid_to, status
FROM customer_price
WHERE customer_id = '<uuid>'
  AND internal_sku = 'SKU-ABC'
ORDER BY min_qty;

-- Test tier selection query
SELECT * FROM customer_price
WHERE customer_id = '<uuid>'
  AND internal_sku = 'SKU-ABC'
  AND currency = 'EUR'
  AND uom = 'PCE'
  AND min_qty <= 150
  AND valid_from <= CURRENT_DATE
  AND (valid_to IS NULL OR valid_to >= CURRENT_DATE)
ORDER BY min_qty DESC
LIMIT 1;
```
