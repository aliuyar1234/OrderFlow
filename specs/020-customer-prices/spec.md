# Feature Specification: Customer Prices & Price Validation

**Feature Branch**: `020-customer-prices`
**Created**: 2025-12-27
**Status**: Draft
**Module**: catalog, validation
**SSOT References**: §5.4.11, §7.4 (Price Check), §8.8 (Price Import), §9.6 (Imports UI), T-502

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import Customer Price List (Priority: P1)

As an administrator, I need to import customer-specific pricing from a CSV file to enable price validation and matching confidence boosting during order processing.

**Why this priority**: Customer prices are the foundation for price validation. Without them, the system cannot detect pricing errors or boost matching confidence. This is the data entry point for the entire price validation feature.

**Independent Test**: Can be fully tested by uploading a customer_prices.csv file, verifying that records are created in the database with correct customer linkage, SKU normalization, and tier support.

**Acceptance Scenarios**:

1. **Given** a CSV with columns `erp_customer_number,internal_sku,currency,uom,unit_price,min_qty`, **When** admin uploads the file, **Then** customer_price records are created with `status=ACTIVE`
2. **Given** a CSV row with `min_qty=100`, **When** import runs, **Then** the customer_price record stores min_qty=100 (tier pricing support)
3. **Given** a CSV with `customer_name="Acme GmbH"` but no `erp_customer_number`, **When** import runs, **Then** the system looks up customer by name and links the price
4. **Given** a CSV with invalid rows (e.g., missing unit_price), **When** import runs, **Then** the import completes for valid rows and returns an error report CSV with row numbers and error messages
5. **Given** a CSV with 10,000 rows, **When** import runs, **Then** import completes within 30 seconds and displays success count

---

### User Story 2 - Price Tier Selection (Priority: P1)

When validating a draft order line, the system must select the correct price tier based on quantity thresholds to ensure accurate price comparison.

**Why this priority**: Multi-tier pricing is a core business requirement. Without correct tier selection, price validation produces false positives (flagging valid tiered prices as mismatches).

**Independent Test**: Can be fully tested by creating customer prices with multiple tiers (e.g., 1→€10, 100→€9, 500→€8), creating a draft line with qty=150, and verifying that the €9 tier is used for validation.

**Acceptance Scenarios**:

1. **Given** price tiers: min_qty 1→€10, 100→€9, 500→€8, **When** line has qty=50, **Then** validator uses €10 tier
2. **Given** price tiers: min_qty 1→€10, 100→€9, 500→€8, **When** line has qty=150, **Then** validator uses €9 tier
3. **Given** price tiers: min_qty 1→€10, 100→€9, 500→€8, **When** line has qty=600, **Then** validator uses €8 tier
4. **Given** price tiers: min_qty 1→€10, 100→€9, **When** line has qty=100 exactly, **Then** validator uses €9 tier (inclusive threshold)
5. **Given** no price tier exists for customer+SKU, **When** validation runs, **Then** no price validation is performed (no PRICE_MISMATCH issue)

---

### User Story 3 - Price Mismatch Detection with Tolerance (Priority: P1)

The system must compare draft line unit prices against expected customer prices, flagging mismatches that exceed the configured tolerance percentage.

**Why this priority**: Price validation is the primary value of customer prices. Detecting pricing errors prevents costly mistakes from reaching ERP and customers.

**Independent Test**: Can be fully tested by setting `price_tolerance_percent=5%`, creating a draft line with a price 10% above expected, and verifying that a PRICE_MISMATCH issue is created.

**Acceptance Scenarios**:

1. **Given** expected price €10.00 with tolerance 5%, **When** line has unit_price €10.30 (3% diff), **Then** no issue is created
2. **Given** expected price €10.00 with tolerance 5%, **When** line has unit_price €10.60 (6% diff), **Then** PRICE_MISMATCH WARNING is created
3. **Given** expected price €10.00 with tolerance 5%, **When** line has unit_price €12.00 (20% diff), **Then** PRICE_MISMATCH ERROR is created (if org config sets threshold for ERROR)
4. **Given** expected price €10.00, **When** line has unit_price €9.50 (-5% diff), **Then** PRICE_MISMATCH WARNING is created (under-pricing also flagged)
5. **Given** line currency differs from customer_price currency, **When** validation runs, **Then** no price validation is performed (currency mismatch)

---

### User Story 4 - Price Confidence Boost in Matching (Priority: P2)

When a draft line has a unit price that matches expected customer pricing (within tolerance), the matching confidence score should be boosted to indicate higher reliability.

**Why this priority**: Price alignment is a strong signal for correct SKU matching. Boosting confidence reduces false positives in "low confidence" warnings. However, matching works without prices, making this secondary.

**Independent Test**: Can be fully tested by creating a draft line with correct SKU and price (within tolerance), running matching, and verifying that match_confidence includes a P_price penalty factor of 1.0.

**Acceptance Scenarios**:

1. **Given** a line matches SKU "ABC" with trigram score 0.85, **When** unit_price matches expected price within tolerance, **Then** P_price=1.0 and final confidence remains 0.85
2. **Given** a line matches SKU "ABC" with trigram score 0.85, **When** unit_price mismatches (beyond tolerance), **Then** P_price=0.85 and final confidence drops to ~0.72
3. **Given** a line matches SKU "ABC" with trigram score 0.85, **When** unit_price mismatches severely (>2x tolerance), **Then** P_price=0.65 and final confidence drops significantly
4. **Given** no customer_price exists for SKU, **When** matching runs, **Then** P_price is not applied (no penalty)

---

### User Story 5 - Manage Customer Prices in UI (Priority: P3)

Administrators need to view, search, and update customer prices through the UI without reimporting the entire CSV.

**Why this priority**: UI management is a quality-of-life improvement. CSV import (P1) covers the primary use case, but inline editing improves usability for corrections.

**Independent Test**: Can be fully tested by opening the customer prices page, searching for a specific SKU, editing a unit_price, and verifying the change persists.

**Acceptance Scenarios**:

1. **Given** admin opens customer prices page, **When** searching for customer "Acme" and SKU "ABC-123", **Then** matching price records are displayed
2. **Given** admin selects a price record, **When** editing unit_price from €10 to €11 and saving, **Then** the price is updated and `updated_at` timestamp changes
3. **Given** admin wants to add a new price tier, **When** clicking "Add Tier" for SKU "ABC-123" and entering min_qty=500 and unit_price=€8, **Then** a new customer_price record is created
4. **Given** admin wants to deactivate a price, **When** setting `status=INACTIVE`, **Then** the price is no longer used for validation or matching
5. **Given** admin bulk-uploads a new CSV, **When** existing prices for same customer+SKU exist, **Then** the system upserts (updates existing or inserts new) based on min_qty

---

### Edge Cases

- What happens when a customer has multiple active price records for the same SKU+UoM+min_qty? (UNIQUE constraint violation; import should fail with error)
- How does system handle price records with `valid_from` in the future? (Not used until valid_from date; filtered out in queries)
- What if a customer_price references a customer or product that is later deleted? (Foreign key constraint prevents deletion; must deactivate prices first)
- What if price tolerance is set to 0%? (Any price deviation creates PRICE_MISMATCH)
- What if a CSV contains non-numeric unit_price values? (Row fails validation; error report includes "Invalid unit_price" with row number)
- What happens when currency conversion is needed (line in USD, price in EUR)? (Out of scope for MVP; prices must match currency or no validation performed)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement `customer_price` table per §5.4.11 schema
- **FR-002**: System MUST support CSV import with columns: `erp_customer_number` or `customer_name`, `internal_sku`, `currency`, `uom`, `unit_price`, `min_qty`, `valid_from`, `valid_to`
- **FR-003**: System MUST normalize `internal_sku` during import using same normalization rules as products
- **FR-004**: System MUST lookup customer by `erp_customer_number` first, then fallback to `customer_name` if provided
- **FR-005**: System MUST validate required fields: customer (resolved), internal_sku, currency, uom, unit_price (> 0)
- **FR-006**: System MUST support optional fields: `min_qty` (default 1), `valid_from` (default NULL), `valid_to` (default NULL), `status` (default ACTIVE)
- **FR-007**: System MUST enforce UNIQUE constraint on (org_id, customer_id, internal_sku, currency, uom, min_qty, valid_from, valid_to)
- **FR-008**: System MUST generate error report CSV for failed rows, including row number and error reason
- **FR-009**: System MUST return import summary: rows processed, rows succeeded, rows failed
- **FR-010**: System MUST implement price tier selection: find max(min_qty) where min_qty <= line.qty
- **FR-011**: System MUST filter prices by date range: `valid_from <= today` AND (`valid_to IS NULL` OR `valid_to >= today`)
- **FR-012**: CSV import upsert behavior: On duplicate key (customer_id, internal_sku, currency, uom, min_qty), UPDATE existing record with new values. Within same CSV file, later rows overwrite earlier rows with same key. Log upsert statistics: {inserted: N, updated: M, unchanged: K}
- **FR-013**: Price tier uniqueness: UNIQUE constraint on (org_id, customer_id, internal_sku, currency, uom, min_qty) prevents tier collisions. If constraint violated during import, reject row with error 'Duplicate price tier'. Tier selection: max(min_qty) WHERE min_qty <= order_qty
- **FR-014**: System MUST calculate price mismatch percentage: `abs(line.unit_price - expected) / expected * 100`
- **FR-015**: System MUST compare mismatch percentage against `org.settings_json.price_tolerance_percent`
- **FR-016**: System MUST create PRICE_MISMATCH issue when mismatch exceeds tolerance (severity: WARNING by default, ERROR if org configured)
- **FR-017**: System MUST create MISSING_PRICE issue (WARNING) when line has no unit_price but customer_price exists
- **FR-018**: System MUST skip price validation when: no customer_price exists, or line currency != price currency, or line has no customer_id
- **FR-019**: System MUST apply price penalty factor (P_price) in matching confidence calculation per §7.4
- **FR-020**: System MUST expose customer prices API: GET `/customer-prices?customer_id=X&internal_sku=Y`
- **FR-021**: System MUST expose import API: POST `/imports/customer-prices` (multipart/form-data CSV upload)
- **FR-022**: System MUST provide UI for customer price search, view, and inline editing (ADMIN/INTEGRATOR only)

### Key Entities *(include if feature involves data)*

- **CustomerPrice** (§5.4.11): Represents customer-specific pricing for a SKU+UoM combination. Supports tiered pricing via `min_qty`, date-based validity, and active/inactive status. Links to customer and product (via internal_sku).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: CSV import with 10,000 rows completes within 30 seconds with 99%+ success rate for valid data
- **SC-002**: Price tier selection correctly identifies applicable tier in 100% of test cases (unit tests)
- **SC-003**: Price mismatch detection with tolerance has 0% false positives and 0% false negatives (integration tests)
- **SC-004**: Price confidence boost (P_price) correctly adjusts matching scores in 100% of component tests
- **SC-005**: Import error report contains accurate row numbers and error messages for all failed rows
- **SC-006**: UNIQUE constraint prevents duplicate price records (verified in integration tests)
- **SC-007**: UI search and edit operations complete within 500ms for datasets up to 100,000 price records

## Dependencies

- **Depends on**:
  - **001-database-setup**: Requires `customer_price` table (§5.4.11)
  - **004-customers**: Requires customer entity with `erp_customer_number` for lookup
  - **011-product-catalog**: Requires product entity with `internal_sku` for validation
  - **002-auth**: Requires ADMIN/INTEGRATOR roles for import and UI access

- **Enables**:
  - **019-validation-engine**: Provides data for price validation rules
  - **012-matching**: Provides data for price-based confidence boosting (P_price)

## Implementation Notes

### CSV Import Process

```
1. Parse CSV → rows[]
2. For each row:
   a. Lookup customer (by erp_customer_number or customer_name)
   b. Validate internal_sku exists in products
   c. Validate required fields (unit_price > 0, currency valid, uom valid)
   d. Normalize internal_sku
   e. Set defaults (min_qty=1, status=ACTIVE)
   f. UPSERT customer_price (ON CONFLICT update unit_price, updated_at)
3. Return summary + error CSV
```

### Price Tier Selection Algorithm

```python
def select_price_tier(customer_id, internal_sku, currency, uom, qty, today):
    prices = query(
        customer_id=customer_id,
        internal_sku=internal_sku,
        currency=currency,
        uom=uom,
        status=ACTIVE,
        valid_from <= today,
        (valid_to IS NULL OR valid_to >= today)
    )

    # Filter tiers where min_qty <= qty
    applicable = [p for p in prices if p.min_qty <= qty]

    if not applicable:
        return None

    # Return tier with highest min_qty (best match)
    return max(applicable, key=lambda p: p.min_qty)
```

### Price Validation Integration

In ValidationEngine:
```python
def validate_line_price(line: DraftOrderLine, draft: DraftOrder, context):
    if not draft.customer_id or not line.unit_price:
        if line.unit_price is None:
            return ValidationIssue(type="MISSING_PRICE", severity=WARNING)
        return None

    expected_price = select_price_tier(
        customer_id=draft.customer_id,
        internal_sku=line.internal_sku,
        currency=draft.currency,
        uom=line.uom,
        qty=line.qty,
        today=date.today()
    )

    if not expected_price:
        return None  # No price data, no validation

    mismatch_pct = abs(line.unit_price - expected_price.unit_price) / expected_price.unit_price * 100
    tolerance = context.org.settings_json.get('price_tolerance_percent', 5.0)

    if mismatch_pct > tolerance:
        severity = ERROR if mismatch_pct > tolerance * 2 else WARNING
        return ValidationIssue(
            type="PRICE_MISMATCH",
            severity=severity,
            message=f"Price {line.unit_price} differs from expected {expected_price.unit_price} by {mismatch_pct:.1f}%",
            details_json={
                "line_price": line.unit_price,
                "expected_price": expected_price.unit_price,
                "mismatch_percent": mismatch_pct,
                "tolerance_percent": tolerance,
                "tier_min_qty": expected_price.min_qty
            }
        )

    return None
```

### Matching Confidence Boost

In MatchingEngine (per §7.4):
```python
def compute_price_penalty(line, draft, match_candidate):
    if not draft.customer_id or not line.unit_price:
        return None  # No penalty applied

    expected_price = select_price_tier(...)
    if not expected_price:
        return None

    mismatch_pct = abs(line.unit_price - expected_price.unit_price) / expected_price.unit_price * 100
    tolerance = context.org.settings_json.get('price_tolerance_percent', 5.0)

    if mismatch_pct <= tolerance:
        return 1.0  # Within tolerance, no penalty
    elif mismatch_pct <= tolerance * 2:
        return 0.85  # Warning level
    else:
        return 0.65  # Severe mismatch
```

### Terminology

Entity class is CustomerPrice, table is customer_price (snake_case). Validation rule 'price_mismatch' references customer_price records. Consistent naming across specs 019 and 020.

### Database Schema Notes

```sql
CREATE TABLE customer_price (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organization(id),
    customer_id UUID NOT NULL REFERENCES customer(id),
    internal_sku TEXT NOT NULL,  -- Normalized
    currency TEXT NOT NULL,
    uom TEXT NOT NULL,
    unit_price NUMERIC(12,4) NOT NULL,
    min_qty NUMERIC(12,3) DEFAULT 1.000,
    valid_from DATE NULL,
    valid_to DATE NULL,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_customer_price UNIQUE (org_id, customer_id, internal_sku, currency, uom, min_qty, valid_from, valid_to),
    CONSTRAINT fk_customer FOREIGN KEY (customer_id) REFERENCES customer(id),
    CONSTRAINT ck_unit_price_positive CHECK (unit_price > 0),
    CONSTRAINT ck_min_qty_positive CHECK (min_qty > 0)
);

CREATE INDEX idx_customer_price_lookup ON customer_price(org_id, customer_id, internal_sku, currency, uom, status);
```

## Testing Strategy

### Unit Tests
- Price tier selection with various qty values
- Price mismatch percentage calculation
- P_price penalty factor calculation
- Date range filtering (valid_from/valid_to)

### Component Tests
- CSV import with valid data → records created
- CSV import with invalid rows → error report generated
- Price validation with multiple tiers → correct tier selected
- Price validation with tolerance → correct severity assigned

### Integration Tests
- End-to-end import: upload CSV → query customer_prices → verify data
- Price validation in draft: create draft → import prices → validation creates PRICE_MISMATCH
- UPSERT behavior: import same customer+SKU twice → updated_at changes, only one record exists
- Matching confidence: create draft with correct price → match_confidence includes P_price=1.0

### E2E Tests
- Admin uploads customer_prices.csv → imports page shows success count → drafts page shows price validation working
- Admin edits price in UI → validation re-runs on existing drafts → new issues appear

## SSOT Compliance Checklist

- [ ] `customer_price` table schema matches §5.4.11
- [ ] CSV import supports columns per §8.8 and §9.6
- [ ] Price tier selection implements §7.4 algorithm (max min_qty <= qty)
- [ ] Price mismatch detection uses org.settings_json.price_tolerance_percent
- [ ] P_price penalty factor implements §7.4 weighting (1.0, 0.85, 0.65)
- [ ] PRICE_MISMATCH issue type matches §7.3
- [ ] MISSING_PRICE issue type matches §7.3
- [ ] Import error report includes row numbers and error messages
- [ ] T-502 acceptance criteria met (staffelpreise work, tolerance applied, mismatch beyond tolerance creates issue)
