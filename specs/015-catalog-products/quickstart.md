# Quickstart: Catalog & Products Management

**Feature**: 015-catalog-products
**Date**: 2025-12-27

## Development Setup

### 1. Database Migration

```bash
cd backend
alembic revision --autogenerate -m "Add product and customer_price tables"
alembic upgrade head
```

### 2. Enable PostgreSQL Extensions

```sql
-- Run in PostgreSQL
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### 3. Run Backend

```bash
uvicorn src.main:app --reload --port 8000
```

### 4. Test Product Import

```bash
# Upload test CSV
curl -X POST http://localhost:8000/api/v1/imports/products \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/products.csv"
```

Expected response:
```json
{
  "total_rows": 100,
  "imported_count": 95,
  "error_count": 5,
  "error_rows": [...]
}
```

## Testing

```bash
# Unit tests
pytest tests/unit/test_product_importer.py -v

# Integration tests
pytest tests/integration/test_product_import_flow.py -v

# Performance test (10k products)
pytest tests/performance/test_large_import.py -v
```

## Common Tasks

### Import Products CSV

Format:
```csv
internal_sku,name,base_uom,description,manufacturer,EAN,category,uom_conversions
SKU-001,Cable 3x1.5mm,M,Electrical cable,Siemens,4011234567890,Cables,"{\"KAR\": {\"to_base\": 100}}"
```

### Import Customer Prices CSV

Format:
```csv
customer_erp_number,internal_sku,currency,uom,unit_price,min_qty,valid_from,valid_to
CUST-123,SKU-001,EUR,M,10.50,1,2025-01-01,2025-12-31
CUST-123,SKU-001,EUR,M,9.80,10,2025-01-01,2025-12-31
CUST-123,SKU-001,EUR,M,9.50,50,2025-01-01,2025-12-31
```

### Search Products

```bash
curl "http://localhost:8000/api/v1/products?search=cable&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

**Issue**: CSV import fails with encoding error
**Solution**: Ensure CSV is UTF-8 or Windows-1252 (auto-detected)

**Issue**: UoM validation rejects valid units
**Solution**: Check against canonical list (ST,M,CM,MM,KG,G,L,ML,KAR,PAL,SET)

**Issue**: Embedding jobs not triggered
**Solution**: Verify Celery worker running, check Redis connection

## References

- **SSOT §5.4.10**: Product schema
- **SSOT §6.2**: UoM standardization
- **SSOT §8.8**: Import API
