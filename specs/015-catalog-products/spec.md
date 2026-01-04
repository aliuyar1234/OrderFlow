# Feature Specification: Catalog & Products Management

**Feature Branch**: `015-catalog-products`
**Created**: 2025-12-27
**Status**: Draft
**Module**: catalog
**SSOT Refs**: §5.4.10 (product), §6.2 (UoM Standardisierung), §8.8 (Product Import), T-401

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Product Import via CSV (Priority: P1)

An Admin uploads a products.csv file containing internal_sku, name, description, base_uom, and optional attributes (manufacturer, EAN, category). The system validates, imports, and reports results with error rows.

**Why this priority**: Foundation for all matching. Products must be imported before orders can be processed.

**Independent Test**: Upload CSV with 100 products → system imports valid rows, reports 5 errors with row numbers → products queryable immediately.

**Acceptance Scenarios**:

1. **Given** CSV with columns: internal_sku, name, base_uom, description, manufacturer, EAN, **When** uploading, **Then** system validates UoM (must be canonical), creates product records, returns summary: X imported, Y errors
2. **Given** CSV row with invalid base_uom="pieces" (not canonical), **When** validating, **Then** row rejected with error "Invalid UoM: pieces. Must be one of: ST,M,CM,MM,KG,G,L,ML,KAR,PAL,SET"
3. **Given** CSV row with duplicate internal_sku, **When** importing, **Then** system updates existing product (upsert), sets updated_source_at=now
4. **Given** import completes with errors, **When** viewing result screen, **Then** shows "95 imported, 5 errors", downloadable error CSV with row numbers and error messages
5. **Given** products imported, **When** querying product API, **Then** products are immediately available for matching

---

### User Story 2 - UoM Conversions Configuration (Priority: P1)

Admin configures UoM conversions for products (e.g., 1 KAR = 12 ST, 1 PAL = 480 ST) enabling order lines with different UoMs to match correctly.

**Why this priority**: DACH B2B orders frequently use pack units (Karton, Palette). UoM conversion is essential for accurate matching and pricing.

**Independent Test**: Product with base_uom=ST, conversion KAR=12 → order line with uom=KAR, qty=5 → matches product, validation passes.

**Acceptance Scenarios**:

1. **Given** product with base_uom=ST, **When** setting uom_conversions_json={"KAR":{"to_base":12},"PAL":{"to_base":480}}, **Then** conversions saved, queryable
2. **Given** order line with uom=KAR, qty=5, internal_sku=X, **When** validating, **Then** system checks product X has KAR conversion, validation passes
3. **Given** order line with uom=KAR but product has no KAR conversion, **When** validating, **Then** creates UOM_INCOMPATIBLE issue (ERROR severity)
4. **Given** import CSV with uom_conversions column (JSON string), **When** importing, **Then** parses JSON, validates structure, stores in uom_conversions_json

---

### User Story 3 - Product Catalog UI with Search (Priority: P2)

Admin views product catalog in a searchable table. Can filter by active/inactive, search by SKU/name, edit products, and toggle active status.

**Why this priority**: Admins need to manage product master data, fix errors, deactivate discontinued products.

**Independent Test**: Search "cable" → results show all products with "cable" in name or description → click product → edit modal opens → change name → save.

**Acceptance Scenarios**:

1. **Given** 1000 products in catalog, **When** viewing catalog UI, **Then** shows paginated table (50 per page) with columns: internal_sku, name, base_uom, active, updated_source_at
2. **Given** Admin searches "CAB", **When** typing in search box, **Then** results filter to products matching "CAB" in internal_sku or name (case-insensitive)
3. **Given** Admin clicks product row, **When** opening edit modal, **Then** shows all fields (sku, name, description, base_uom, uom_conversions, attributes_json, active), allows editing
4. **Given** Admin toggles active=false, **When** saving, **Then** product.active=false, product hidden from matching (only active products considered)
5. **Given** Admin edits product name, **When** saving, **Then** updated_source_at is updated, embedding recompute job is enqueued (§7.7.4)

---

### User Story 4 - Customer-Specific Pricing Import (Priority: P2)

Admin uploads customer_prices.csv containing customer_id, internal_sku, currency, uom, unit_price, min_qty (for tier pricing), and validity dates. System imports and uses for price validation.

**Why this priority**: DACH B2B requires customer-specific net prices and tier pricing (Staffelpreise). Price validation depends on this data.

**Independent Test**: Upload prices CSV with 3 tiers for SKU-123 (min_qty 1/10/50) → order with qty=15 → system selects tier with min_qty=10 for price validation.

**Acceptance Scenarios**:

1. **Given** CSV with columns: customer_id, internal_sku, currency, uom, unit_price, min_qty, valid_from, valid_to, **When** importing, **Then** system validates customer/product exist, creates customer_price records
2. **Given** multiple rows for same customer+sku with different min_qty (tier pricing), **When** importing, **Then** all tiers imported
3. **Given** order line with customer_id=A, internal_sku=X, qty=15, **When** validating price, **Then** system finds all customer_prices for A+X, selects tier with max(min_qty) WHERE min_qty <= 15, compares unit_price
4. **Given** order line price within tolerance (±5% default), **When** validating, **Then** no issue created
5. **Given** order line price exceeds tolerance, **When** validating, **Then** creates PRICE_MISMATCH issue (WARNING severity, or ERROR if configured)

---

### User Story 5 - Product Attributes and Search (Priority: P3)

Products store arbitrary attributes (manufacturer, EAN, category) in attributes_json. Search/filter includes attributes for better matching context.

**Why this priority**: Enriches product data for LLM context and fuzzy matching. Manufacturer/EAN often appear in orders.

**Independent Test**: Import product with attributes {"manufacturer":"Siemens","EAN":"4011234567890"} → search by EAN → product found.

**Acceptance Scenarios**:

1. **Given** CSV includes columns: manufacturer, EAN, category, **When** importing, **Then** values stored in attributes_json as {"manufacturer":"X","EAN":"Y","category":"Z"}
2. **Given** product with attributes_json, **When** generating embedding text per §7.7.3, **Then** attributes included in format "ATTR: {manufacturer};{ean};{category}"
3. **Given** Admin searches by EAN in UI, **When** querying, **Then** JSONB query on attributes_json->'EAN' matches
4. **Given** order extraction includes manufacturer in description, **When** matching, **Then** manufacturer attribute boosts semantic match score

---

### Edge Cases

- What happens when CSV encoding is Windows-1252 instead of UTF-8?
- How does system handle CSV with missing required columns (internal_sku, name)?
- What happens when importing 10k+ products (performance, timeout)?
- How does system handle product deletion (cascade to embeddings, mappings, prices)?
- What happens when customer_prices CSV references non-existent customer_id or internal_sku?
- How does system handle product SKU conflicts (same SKU across different orgs)?

## Requirements *(mandatory)*

### Functional Requirements

**Product Entity:**
- **FR-001**: System MUST define product entity per §5.4.10 with fields:
  - internal_sku (TEXT, unique per org)
  - name (TEXT, required)
  - description (TEXT, optional)
  - base_uom (TEXT, must be canonical UoM per §6.2)
  - uom_conversions_json (JSONB, default '{}', format: `{"KAR":{"to_base":12}}`)
  - active (BOOLEAN, default true)
  - attributes_json (JSONB, default '{}', e.g., `{"manufacturer":"X","EAN":"Y"}`)
  - updated_source_at (TIMESTAMPTZ, set on import/edit)
- **FR-002**: System MUST enforce UNIQUE constraint on (org_id, internal_sku)
- **FR-003**: System MUST validate base_uom against canonical list: ST, M, CM, MM, KG, G, L, ML, KAR, PAL, SET
- **FR-004**: System MUST validate uom_conversions_json structure: keys are UoM codes, values are `{"to_base": number}`

**Product Import:**
- **FR-005**: System MUST accept CSV upload with columns:
  - Required: internal_sku, name, base_uom
  - Optional: description, manufacturer, EAN, category, uom_conversions (JSON string)
- **FR-006**: System MUST detect CSV encoding (UTF-8, Windows-1252) and parse correctly
- **FR-007**: System MUST validate each row:
  - internal_sku not empty
  - base_uom in canonical list
  - uom_conversions valid JSON (if present)
- **FR-008**: System MUST perform UPSERT on (org_id, internal_sku):
  - If exists: update name, description, uom_conversions, attributes, set updated_source_at=now
  - If new: insert with created_at=now, updated_source_at=now
- **FR-009**: System MUST return import result:
  - total_rows, imported_count, error_count
  - error_rows array: [{row_number, internal_sku, error_message}]
- **FR-010**: System MUST generate downloadable error CSV if errors exist
- **FR-011**: System MUST enqueue embedding recompute jobs for new/updated products per §7.7.4

**UoM Conversions:**
- **FR-012**: System MUST support UoM conversion lookup:
  - Given product and target_uom, return to_base factor or null if not supported
- **FR-013**: System MUST validate order line UoM compatibility:
  - If line.uom == product.base_uom → compatible
  - If line.uom in product.uom_conversions_json → compatible
  - Else → UOM_INCOMPATIBLE issue

**Customer Prices:**
- **FR-014**: System MUST define customer_price entity per §5.4.11 with fields:
  - customer_id, internal_sku, currency, uom, unit_price, min_qty (default 1), valid_from, valid_to, source (default 'IMPORT')
- **FR-015**: System MUST accept customer_prices CSV with columns:
  - Required: customer_id (or customer_erp_number for lookup), internal_sku, currency, uom, unit_price
  - Optional: min_qty, valid_from, valid_to
- **FR-016**: System MUST validate customer and product exist before import
- **FR-017**: System MUST support tier pricing:
  - Multiple rows for same customer+sku with different min_qty
  - Query: SELECT * WHERE customer_id=X AND internal_sku=Y AND min_qty <= line.qty ORDER BY min_qty DESC LIMIT 1
- **FR-018**: System MUST validate dates: valid_from <= valid_to, prices only active within date range

**Product Catalog UI:**
- **FR-019**: UI MUST display product table with pagination (50 per page)
- **FR-020**: UI MUST support search (filter by internal_sku, name, description)
- **FR-021**: UI MUST support filter by active status
- **FR-022**: UI MUST allow editing product fields via modal
- **FR-023**: UI MUST allow toggling active status
- **FR-024**: UI MUST display updated_source_at to show freshness

### Key Entities

- **product** (§5.4.10): Core product master data
- **customer_price** (§5.4.11): Customer-specific tier pricing
- **UoM Conversions**: JSONB structure for unit conversions
- **Canonical UoM List**: ST, M, CM, MM, KG, G, L, ML, KAR, PAL, SET

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Product import handles 10k products in <30 seconds
- **SC-002**: CSV validation catches 100% of invalid UoMs before import
- **SC-003**: Upsert logic correctly updates existing products in 100% of cases
- **SC-004**: UoM conversion lookup performs in <1ms (indexed)
- **SC-005**: Customer price tier selection is accurate in 100% of test cases
- **SC-006**: Product search returns results in <200ms for 10k product catalog
- **SC-007**: Error CSV generation includes all failed rows with actionable messages
- **SC-008**: Embedding recompute jobs are enqueued for 100% of updated products

## Dependencies

- **Depends on**:
  - Database (product, customer_price tables)
  - Customer entity (for customer_price FK)
  - Object storage (for CSV uploads)
  - Worker queue (for embedding recompute jobs)

- **Blocks**:
  - 017-matching-engine (requires products to match against)
  - 016-embedding-layer (requires products to embed)
  - Validation service (requires customer_price for price checks)

## Technical Notes

### Implementation Guidance

**Multi-Tenant Isolation:** Product is org-scoped via UNIQUE constraint (org_id, internal_sku) per FR-002. uom_conversions_json inherits org isolation through product.org_id foreign key. No cross-org data leakage possible if product FK constraints are properly enforced.

**CSV Import Performance:** (1) Batch imports into chunks of 1000 rows, (2) Use PostgreSQL COPY FROM or bulk INSERT with prepared statements, (3) Temporarily disable non-essential indexes during large imports (>5000 rows), (4) Recreate/refresh indexes after import completes. Target: 10k products in <30s per SC-004.

**CSV Import Service:**
```python
import csv
import chardet
from io import StringIO

def import_products_csv(org_id: UUID, file_bytes: bytes) -> ImportResult:
    # Detect encoding
    encoding = chardet.detect(file_bytes)['encoding']
    text = file_bytes.decode(encoding)

    reader = csv.DictReader(StringIO(text))
    results = {"total": 0, "imported": 0, "errors": []}

    for row_num, row in enumerate(reader, start=2):  # start=2 (header is row 1)
        results["total"] += 1
        try:
            validate_product_row(row)
            upsert_product(org_id, row)
            results["imported"] += 1
        except ValidationError as e:
            results["errors"].append({
                "row": row_num,
                "sku": row.get("internal_sku"),
                "error": str(e)
            })

    # Enqueue embedding jobs for updated products
    enqueue_embedding_recompute_jobs(org_id)

    return results

def validate_product_row(row: dict):
    if not row.get("internal_sku"):
        raise ValidationError("internal_sku required")
    if not row.get("name"):
        raise ValidationError("name required")
    if row.get("base_uom") not in CANONICAL_UOMS:
        raise ValidationError(f"Invalid base_uom: {row['base_uom']}")
    if row.get("uom_conversions"):
        try:
            json.loads(row["uom_conversions"])
        except:
            raise ValidationError("Invalid JSON in uom_conversions")

def upsert_product(org_id: UUID, row: dict):
    product = db.query(Product).filter(
        Product.org_id == org_id,
        Product.internal_sku == row["internal_sku"]
    ).first()

    attributes = {}
    if row.get("manufacturer"):
        attributes["manufacturer"] = row["manufacturer"]
    if row.get("EAN"):
        attributes["EAN"] = row["EAN"]
    if row.get("category"):
        attributes["category"] = row["category"]

    uom_conversions = {}
    if row.get("uom_conversions"):
        uom_conversions = json.loads(row["uom_conversions"])

    if product:
        product.name = row["name"]
        product.description = row.get("description")
        product.base_uom = row["base_uom"]
        product.uom_conversions_json = uom_conversions
        product.attributes_json = attributes
        product.updated_source_at = now()
    else:
        product = Product(
            org_id=org_id,
            internal_sku=row["internal_sku"],
            name=row["name"],
            description=row.get("description"),
            base_uom=row["base_uom"],
            uom_conversions_json=uom_conversions,
            attributes_json=attributes,
            updated_source_at=now()
        )
        db.add(product)

    db.commit()
```

**UoM Compatibility Check:**
```python
def is_uom_compatible(product: Product, target_uom: str) -> bool:
    if target_uom == product.base_uom:
        return True
    if target_uom in product.uom_conversions_json:
        return True
    return False

def get_conversion_factor(product: Product, from_uom: str) -> float | None:
    if from_uom == product.base_uom:
        return 1.0
    conv = product.uom_conversions_json.get(from_uom)
    if conv and "to_base" in conv:
        return conv["to_base"]
    return None
```

**Customer Price Lookup (Tier):**
```python
def get_customer_price(customer_id: UUID, internal_sku: str, qty: float, currency: str, uom: str, order_date: date) -> CustomerPrice | None:
    prices = db.query(CustomerPrice).filter(
        CustomerPrice.org_id == org_id,
        CustomerPrice.customer_id == customer_id,
        CustomerPrice.internal_sku == internal_sku,
        CustomerPrice.currency == currency,
        CustomerPrice.uom == uom,
        CustomerPrice.min_qty <= qty,
        or_(
            CustomerPrice.valid_from.is_(None),
            CustomerPrice.valid_from <= order_date
        ),
        or_(
            CustomerPrice.valid_to.is_(None),
            CustomerPrice.valid_to >= order_date
        )
    ).order_by(CustomerPrice.min_qty.desc()).first()

    return prices
```

**Product Search (Fulltext + JSONB):**
```sql
-- Index for search
CREATE INDEX idx_product_search ON product USING GIN (to_tsvector('simple', name || ' ' || COALESCE(description, '')));
CREATE INDEX idx_product_attributes ON product USING GIN (attributes_json);

-- Query
SELECT * FROM product
WHERE org_id = :org_id
  AND active = true
  AND (
    to_tsvector('simple', name || ' ' || COALESCE(description, '')) @@ plainto_tsquery('simple', :search)
    OR internal_sku ILIKE :search_wildcard
    OR attributes_json->>'EAN' = :search
  )
LIMIT 50 OFFSET :offset;
```

### Testing Strategy

**Unit Tests:**
- CSV parsing: various encodings, column orders
- Product validation: missing fields, invalid UoMs
- Upsert logic: new products, existing products
- UoM compatibility: various conversion scenarios
- Price tier selection: various qty/min_qty combinations

**Integration Tests:**
- End-to-end: upload CSV → products imported → queryable via API
- Customer price import → price validation uses tiers correctly
- Product edit → embedding recompute enqueued

**Performance Tests:**
- Import 10k products: <30s
- Search 10k products: <200ms
- Price lookup with 1000 tiers per SKU: <10ms

## SSOT References

- **§5.4.10**: product table schema
- **§5.4.11**: customer_price table schema
- **§6.2**: UoM Standardization and canonical codes
- **§7.4**: Validation Rules (UoM compatibility, price checks)
- **§7.7.3**: Product embedding text format (includes attributes)
- **§7.7.4**: Embedding indexing strategy (recompute on product update)
- **§8.8**: Product Import API
- **T-401**: Product Catalog task
