# Research: Customer Prices

**Date**: 2025-12-27

## Key Decisions

### Decision 1: Tier Selection Algorithm
**Selected**: `max(min_qty) WHERE min_qty <= line.qty AND valid_from <= today AND (valid_to IS NULL OR valid_to >= today)`

**Rationale**: Standard quantity-break pricing. SQL query is fast with proper indexes.

### Decision 2: Price Tolerance as Percentage
**Selected**: `mismatch_pct = abs(line.unit_price - expected) / expected * 100`

**Rationale**: Percentage-based tolerance is intuitive for business users. Handles different price ranges (€1 vs €1000).

### Decision 3: UPSERT for CSV Import
**Selected**: `ON CONFLICT (customer_id, internal_sku, currency, uom, min_qty, valid_from, valid_to) DO UPDATE SET unit_price = EXCLUDED.unit_price`

**Rationale**: Re-importing same file updates prices, doesn't create duplicates. Idempotent.

## Best Practices

### CSV Format
```csv
erp_customer_number,internal_sku,currency,uom,unit_price,min_qty,valid_from,valid_to
CUST-001,SKU-ABC,EUR,PCE,10.00,1,,
CUST-001,SKU-ABC,EUR,PCE,9.00,100,,
CUST-001,SKU-ABC,EUR,PCE,8.00,500,,
```

### Tier Selection Query
```sql
SELECT *
FROM customer_price
WHERE customer_id = :customer_id
  AND internal_sku = :sku
  AND currency = :currency
  AND uom = :uom
  AND status = 'ACTIVE'
  AND min_qty <= :qty
  AND valid_from <= :today
  AND (valid_to IS NULL OR valid_to >= :today)
ORDER BY min_qty DESC
LIMIT 1;
```
