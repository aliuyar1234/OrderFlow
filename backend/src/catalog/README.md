# Catalog Module

Product master data management for OrderFlow.

## Overview

The catalog module provides comprehensive product and unit of measure (UoM) management capabilities, including:

- Product CRUD operations
- CSV import with automatic encoding detection
- UoM conversions and validation
- Advanced search with full-text indexing
- Multi-tenant isolation
- Flexible product attributes (JSONB)

## Module Structure

```
catalog/
├── __init__.py           # Module exports
├── schemas.py            # Pydantic validation schemas
├── router.py             # FastAPI endpoints
├── import_service.py     # CSV import business logic
└── README.md            # This file
```

## Key Components

### Schemas (`schemas.py`)

**Product Schemas:**
- `ProductBase` - Base product fields
- `ProductCreate` - Product creation schema
- `ProductUpdate` - Product update schema (partial)
- `ProductResponse` - API response schema
- `ProductSearchParams` - Search query parameters

**UoM Schemas:**
- `UnitOfMeasureCreate` - UoM creation schema
- `UnitOfMeasureUpdate` - UoM update schema
- `UnitOfMeasureResponse` - API response schema

**Import Schemas:**
- `ProductImportRow` - CSV row structure
- `ProductImportError` - Error reporting
- `ProductImportResult` - Import summary

**Validation:**
- Canonical UoM codes: `ST, M, CM, MM, KG, G, L, ML, KAR, PAL, SET`
- UoM conversions JSON structure validation
- Required fields enforcement

### Router (`router.py`)

**Product Endpoints:**
- `POST /products` - Create product
- `GET /products` - List with search/pagination
- `GET /products/{id}` - Get single product
- `PATCH /products/{id}` - Update product
- `POST /products/import` - CSV import
- `POST /products/import/errors` - Download error CSV

**UoM Endpoints:**
- `POST /products/uom` - Create UoM
- `GET /products/uom` - List UoMs

**Role-Based Access:**
- ADMIN, INTEGRATOR: Full access (create, update, import)
- OPS: Update existing products
- VIEWER: Read-only access

### Import Service (`import_service.py`)

**ProductImportService:**
- `import_from_csv(file_bytes)` - Import products from CSV
- Automatic encoding detection (UTF-8, Windows-1252, etc.)
- Upsert logic (update existing, insert new)
- Row-level error handling
- Detailed error reporting

**Helper Functions:**
- `generate_error_csv(result)` - Generate error CSV for download

## Usage Examples

### 1. Create a Product

```python
from catalog.schemas import ProductCreate

product_data = ProductCreate(
    internal_sku="PROD-001",
    name="Sample Product",
    base_uom="ST",
    description="A sample product",
    uom_conversions_json={
        "KAR": {"to_base": 12},
        "PAL": {"to_base": 480}
    },
    attributes_json={
        "manufacturer": "ACME Corp",
        "ean": "1234567890123",
        "category": "Electronics"
    }
)
```

### 2. Import Products from CSV

```python
from catalog.import_service import ProductImportService

# Read CSV file
with open("products.csv", "rb") as f:
    file_bytes = f.read()

# Import
service = ProductImportService(db, org_id)
result = service.import_from_csv(file_bytes)

print(f"Imported: {result.imported_count}")
print(f"Errors: {result.error_count}")
```

### 3. Search Products

```python
from sqlalchemy import select
from models.product import Product

# Search by SKU or name
query = select(Product).where(
    Product.org_id == org_id,
    Product.active == True,
    or_(
        Product.internal_sku.ilike("%cable%"),
        Product.name.ilike("%cable%")
    )
)

products = db.execute(query).scalars().all()
```

## CSV Import Format

### Required Columns
- `internal_sku` - Unique product SKU
- `name` - Product name
- `base_uom` - Base unit of measure (must be canonical)

### Optional Columns
- `description` - Product description
- `manufacturer` - Manufacturer name (stored in attributes_json)
- `ean` - EAN barcode (stored in attributes_json)
- `category` - Product category (stored in attributes_json)
- `uom_conversions` - JSON string with conversions

### Example CSV

```csv
internal_sku,name,base_uom,description,manufacturer,ean,category,uom_conversions
PROD-001,Product 1,ST,Description,ACME,1234567890123,Electronics,"{""KAR"":{""to_base"":12}}"
PROD-002,Product 2,KG,Description,Beta,9876543210987,Materials,
PROD-003,Product 3,L,Description,Gamma,1111222233334,Chemicals,
```

## Database Schema

### Product Table

```sql
CREATE TABLE product (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(id),
    internal_sku TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    base_uom TEXT NOT NULL,
    uom_conversions_json JSONB NOT NULL DEFAULT '{}',
    active BOOLEAN NOT NULL DEFAULT true,
    attributes_json JSONB NOT NULL DEFAULT '{}',
    updated_source_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_product_org_sku UNIQUE (org_id, internal_sku)
);
```

**Indexes:**
- `idx_product_org_sku` - (org_id, internal_sku)
- `idx_product_org_name` - (org_id, name)
- `idx_product_org_active` - (org_id, active)
- `idx_product_search` - GIN index for full-text search
- `idx_product_attributes` - GIN index for JSONB attributes

### UnitOfMeasure Table

```sql
CREATE TABLE unit_of_measure (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    conversion_factor NUMERIC(10, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_unit_of_measure_org_code UNIQUE (org_id, code)
);
```

## Multi-Tenant Isolation

All queries are automatically filtered by `org_id`:
- Products are unique per organization (org_id + internal_sku)
- Users can only access their organization's data
- Cross-tenant access returns 404 (not 403) to prevent information disclosure

## Performance

**Optimizations:**
- GIN indexes for full-text search (name, description)
- GIN indexes for JSONB attribute queries
- B-tree indexes for exact matches (SKU, name)
- Pagination support (limit/offset)

**Targets:**
- CSV import: 10k products in <30 seconds
- Product search: <200ms for 10k products
- Concurrent imports: 50 users

## Error Handling

**Validation Errors:**
- Invalid UoM codes (not in canonical list)
- Missing required fields (internal_sku, name, base_uom)
- Invalid JSON in uom_conversions
- Duplicate SKU (returns existing product ID)

**Import Errors:**
- Row-level error tracking with line numbers
- Detailed error messages
- Downloadable error CSV
- Continues processing after errors

## Testing

**Unit Tests:** (to be implemented)
- Schema validation
- CSV parsing with various encodings
- Upsert logic
- UoM validation

**Integration Tests:** (to be implemented)
- End-to-end import flow
- Product CRUD operations
- Search and pagination
- Multi-tenant isolation

## Dependencies

- `chardet` - CSV encoding detection
- `pandas` - CSV processing
- `sqlalchemy` - Database ORM
- `pydantic` - Schema validation
- `fastapi` - API framework

## SSOT References

- §5.4.10 - Product table schema
- §6.2 - UoM standardization
- §8.8 - Product import API
- T-401 - Product catalog task
