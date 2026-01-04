# Customer Pricing Module

This module implements customer-specific pricing with tiered pricing support, date-based validity, and integration with the validation engine.

## Overview

Per SSOT §5.4.11 and spec 020-customer-prices, the customer pricing system provides:

- **Customer-specific prices**: Store negotiated prices for each customer/product combination
- **Tiered pricing**: Support quantity-based price breaks (staffelpreise)
- **Date-based validity**: Prices can have valid_from and valid_to dates
- **Multi-currency and UoM support**: Prices are specific to currency and unit of measure
- **CSV import**: Bulk import prices with UPSERT behavior
- **Price validation**: Automatically validate draft order prices against customer prices
- **Price-based matching confidence**: Boost SKU matching confidence when prices align

## Database Schema

### customer_price table

```sql
CREATE TABLE customer_price (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES org(id),
    customer_id UUID NOT NULL REFERENCES customer(id),
    internal_sku TEXT NOT NULL,
    currency TEXT NOT NULL,
    uom TEXT NOT NULL,
    unit_price NUMERIC(18,4) NOT NULL,
    min_qty NUMERIC(18,3) DEFAULT 1.000,
    valid_from DATE NULL,
    valid_to DATE NULL,
    source TEXT DEFAULT 'IMPORT',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Key fields:**
- `min_qty`: Minimum quantity for this price tier (default 1.000)
- `valid_from`/`valid_to`: Optional date range for price validity
- `source`: Origin of price (IMPORT, MANUAL, etc.)

**Indexes:**
- `idx_customer_price_lookup`: (org_id, customer_id, internal_sku)
- `idx_customer_price_tier_lookup`: (org_id, customer_id, internal_sku, min_qty)

## Core Components

### 1. PriceService (service.py)

Main service for price operations:

**Key methods:**
- `select_price_tier()`: Find the best matching price tier for a given quantity
- `get_customer_prices()`: Query prices with filters and pagination
- `create_price()`: Create a new customer price
- `update_price()`: Update an existing price
- `delete_price()`: Delete a price

**Price Tier Selection Algorithm:**
```python
1. Filter prices by:
   - customer_id, internal_sku, currency, uom
   - valid_from <= as_of_date (or NULL)
   - valid_to >= as_of_date (or NULL)
   - min_qty <= order_qty

2. Select tier with highest min_qty (best match for quantity)
3. Return that tier's unit_price
```

**Example:**
```python
from pricing.service import PriceService

# Find price for 150 units
price = PriceService.select_price_tier(
    db=db,
    org_id=org_id,
    customer_id=customer_id,
    internal_sku="SKU-001",
    currency="EUR",
    uom="EA",
    qty=Decimal("150.000")
)

# If price tiers exist: 1→€10, 100→€9, 500→€8
# Returns tier with min_qty=100 and unit_price=€9
```

### 2. PriceImportService (import_service.py)

CSV import service with UPSERT behavior:

**CSV Format (per §8.8):**
```csv
erp_customer_number,internal_sku,currency,uom,unit_price,min_qty,valid_from,valid_to
CUST001,SKU-001,EUR,EA,10.00,1,,
CUST001,SKU-001,EUR,EA,9.00,100,,
CUST001,SKU-001,EUR,EA,8.00,500,2025-01-01,2025-12-31
```

**Required columns:**
- `erp_customer_number` OR `customer_name` (one required)
- `internal_sku`
- `currency`
- `uom`
- `unit_price`

**Optional columns:**
- `min_qty` (default: 1.000)
- `valid_from` (YYYY-MM-DD format)
- `valid_to` (YYYY-MM-DD format)

**UPSERT behavior:**
- If price exists with same (customer_id, internal_sku, currency, uom, min_qty), UPDATE
- Otherwise, INSERT
- Later rows in CSV overwrite earlier rows with same key

**Example:**
```python
from pricing.import_service import PriceImportService

import_service = PriceImportService(db, org_id)
result = import_service.import_prices(csv_file)

print(f"Imported: {result.imported}")
print(f"Updated: {result.updated}")
print(f"Failed: {result.failed}")
for error in result.errors:
    print(f"Row {error['row']}: {error['error']}")
```

### 3. Price Validation (domain/validation/rules/price_rules.py)

Integrated into ValidationEngine, automatically validates draft order line prices:

**Validation rules:**
1. **MISSING_PRICE**: Warning if line.unit_price is NULL
2. **PRICE_MISMATCH**: Warning/Error if price deviation exceeds tolerance

**Tolerance check:**
```python
deviation_pct = abs(line_price - expected_price) / expected_price * 100

if deviation_pct > org.settings_json.price_tolerance_percent:
    # Create PRICE_MISMATCH issue
```

**Org settings:**
- `price_tolerance_percent`: Allowed deviation (default: 5.0%)
- `price_mismatch_severity`: "WARNING" or "ERROR"

**Example validation issue:**
```json
{
  "type": "PRICE_MISMATCH",
  "severity": "WARNING",
  "message": "Line 1: Price EUR 10.60 deviates 6.0% from expected 10.00 (tolerance: 5.0%)",
  "details": {
    "actual_price": "10.60",
    "expected_price": "10.00",
    "deviation_percent": 6.0,
    "tolerance_percent": 5.0,
    "tier_min_qty": "1.000"
  }
}
```

## API Endpoints

### Customer Price CRUD

**Create price:**
```http
POST /customer-prices
Authorization: Bearer <token>
Content-Type: application/json

{
  "customer_id": "uuid",
  "internal_sku": "SKU-001",
  "currency": "EUR",
  "uom": "EA",
  "unit_price": 10.00,
  "min_qty": 1.000,
  "valid_from": "2025-01-01",
  "valid_to": "2025-12-31",
  "source": "MANUAL"
}
```

**List prices (with filters):**
```http
GET /customer-prices?customer_id=uuid&internal_sku=SKU-001&currency=EUR&page=1&per_page=100
Authorization: Bearer <token>
```

**Update price:**
```http
PATCH /customer-prices/{price_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "unit_price": 12.00
}
```

**Delete price:**
```http
DELETE /customer-prices/{price_id}
Authorization: Bearer <token>
```

### Price Lookup

**Lookup best matching price tier:**
```http
POST /customer-prices/lookup
Authorization: Bearer <token>
Content-Type: application/json

{
  "customer_id": "uuid",
  "internal_sku": "SKU-001",
  "currency": "EUR",
  "uom": "EA",
  "qty": 150.000,
  "date": "2025-01-04"
}
```

Response:
```json
{
  "found": true,
  "unit_price": 9.00,
  "min_qty": 100.000,
  "valid_from": null,
  "valid_to": null,
  "price_id": "uuid"
}
```

### CSV Import

**Import customer prices:**
```http
POST /customer-prices/import
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <customer_prices.csv>
```

Response:
```json
{
  "imported": 45,
  "updated": 12,
  "failed": 2,
  "errors": [
    {
      "row": 15,
      "error": "Customer with ERP number 'CUST999' not found"
    },
    {
      "row": 23,
      "error": "Invalid unit_price value 'N/A'"
    }
  ]
}
```

## Testing

### Unit Tests

Located in `tests/unit/pricing/test_price_tier_selection.py`

**Test coverage:**
- Single tier selection
- Multiple tier selection (lowest, middle, highest qty)
- Exact min_qty boundary
- No price found scenarios
- Date range filtering (valid_from, valid_to)
- Currency and UoM filtering

**Run tests:**
```bash
pytest tests/unit/pricing/
```

### Integration Tests

Located in `tests/integration/pricing/test_csv_import.py`

**Test coverage:**
- Valid CSV import
- Customer lookup (by ERP number and name)
- Optional fields (dates)
- Missing required fields
- Invalid data (unit_price, dates)
- Customer not found
- UPSERT behavior
- Multiple rows (success and failure)
- Duplicate keys within CSV
- SKU normalization
- Negative prices
- Invalid date formats

**Run tests:**
```bash
pytest tests/integration/pricing/
```

## Usage Examples

### Example 1: Import customer prices from CSV

```python
# In your application code
from pricing.import_service import PriceImportService

# Read CSV file
with open('customer_prices.csv', 'rb') as f:
    import_service = PriceImportService(db, org_id)
    result = import_service.import_prices(f)

    if result.failed > 0:
        logger.warning(f"Import had {result.failed} failures")
        for error in result.errors:
            logger.error(f"Row {error['row']}: {error['error']}")
```

### Example 2: Lookup price for draft order validation

```python
from pricing.service import PriceService

# During draft order validation
price = PriceService.select_price_tier(
    db=db,
    org_id=draft_order.org_id,
    customer_id=draft_order.customer_id,
    internal_sku=line.internal_sku,
    currency=draft_order.currency,
    uom=line.uom,
    qty=line.qty
)

if price:
    expected_price = price.unit_price
    if abs(line.unit_price - expected_price) / expected_price > tolerance:
        # Create PRICE_MISMATCH validation issue
        pass
```

### Example 3: Create price tiers programmatically

```python
from pricing.service import PriceService
from decimal import Decimal

# Create volume-based pricing tiers
tiers = [
    (Decimal("1.000"), Decimal("10.00")),
    (Decimal("100.000"), Decimal("9.00")),
    (Decimal("500.000"), Decimal("8.00")),
]

for min_qty, unit_price in tiers:
    PriceService.create_price(
        db=db,
        org_id=org_id,
        customer_id=customer_id,
        internal_sku="SKU-001",
        currency="EUR",
        uom="EA",
        unit_price=unit_price,
        min_qty=min_qty,
        source="MANUAL"
    )
```

## Matching Confidence Integration

Per §7.4, customer prices also boost SKU matching confidence via the P_price penalty factor:

**Logic:**
- If price within tolerance: P_price = 1.0 (no penalty)
- If price mismatch (warning level): P_price = 0.85
- If severe mismatch (>2x tolerance): P_price = 0.65
- If no customer price exists: P_price not applied

**Implementation:**
Located in `domain/matching/` (to be implemented in future spec)

## Configuration

**Organization settings (org.settings_json):**

```json
{
  "price_tolerance_percent": 5.0,
  "price_mismatch_severity": "WARNING"
}
```

**Default values:**
- `price_tolerance_percent`: 5.0 (5% deviation allowed)
- `price_mismatch_severity`: "WARNING" (can be "ERROR" to block approval)

## Migration

**Migration file:** `backend/migrations/versions/005_create_customer_price_table.py`

**To apply migration:**
```bash
cd backend
alembic upgrade head
```

**To rollback:**
```bash
alembic downgrade -1
```

## Dependencies

- SQLAlchemy 2.x (ORM)
- FastAPI (API endpoints)
- Pydantic (schema validation)
- pandas (CSV parsing)
- PostgreSQL 16+ (database)

## Future Enhancements

Potential features not in MVP scope:

1. **Price history tracking**: Keep audit trail of price changes
2. **Automatic price updates**: Scheduled jobs to update prices from ERP
3. **Price approval workflow**: Require approval for price changes above threshold
4. **Currency conversion**: Auto-convert prices when order currency differs
5. **Price comparison report**: Show price deviations across customers
6. **Price caching**: Redis cache for frequently accessed prices
7. **Bulk price updates**: UI for editing multiple prices at once
8. **Price import templates**: Downloadable CSV templates with examples

## See Also

- **SSOT_SPEC.md §5.4.11**: Database schema definition
- **specs/020-customer-prices/spec.md**: Feature specification
- **specs/020-customer-prices/plan.md**: Implementation plan
- **domain/validation/rules/price_rules.py**: Price validation logic
