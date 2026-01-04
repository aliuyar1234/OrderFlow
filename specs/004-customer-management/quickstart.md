# Quickstart: Customer Management

**Feature**: 004-customer-management
**Date**: 2025-12-27
**Prerequisites**: 001-platform-foundation, 002-auth-rbac, 003-tenancy-isolation

## Quick Start

### 1. Run Migrations

```bash
alembic upgrade head
```

### 2. Create Test Customer via API

```bash
# Login as ADMIN
curl -X POST http://localhost:8000/auth/login \
  -d '{"org_slug": "test-org", "email": "admin@test-org.com", "password": "password123"}'

TOKEN="..."

# Create customer
curl -X POST http://localhost:8000/customers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Muster GmbH",
    "erp_customer_number": "4711",
    "default_currency": "EUR",
    "default_language": "de-DE",
    "billing_address": {
      "street": "Musterstraße 1",
      "city": "München",
      "postal_code": "80331",
      "country": "DE"
    }
  }'

# Response: {"id": "customer-uuid", ...}
```

### 3. Add Contact to Customer

```bash
CUSTOMER_ID="customer-uuid-from-above"

curl -X POST http://localhost:8000/customers/$CUSTOMER_ID/contacts \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "email": "einkauf@muster.de",
    "name": "Max Mustermann",
    "is_primary": true
  }'
```

### 4. Import Customers from CSV

Use the sample CSV file `docs/sample_customers.csv` (contains 10 DACH region customers) or create your own:

```csv
name,erp_customer_number,default_currency,default_language,billing_street,billing_city,billing_postal_code,billing_country,contact_email,contact_name,contact_is_primary
"Muster GmbH",4711,EUR,de-DE,"Musterstraße 1",München,80331,DE,einkauf@muster.de,"Max Mustermann",true
"Acme AG",4712,CHF,de-CH,"Acmestr. 10",Zürich,8001,CH,order@acme.ch,"Hans Meier",true
```

Upload via API:
```bash
# Using sample file
curl -X POST http://localhost:8000/imports/customers \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/sample_customers.csv"

# Response:
# {
#   "imported": 10,
#   "updated": 0,
#   "failed": 0,
#   "errors": []
# }
```

See `docs/customer_import_guide.md` for complete CSV format documentation.

### 5. Search Customers

```bash
# List all customers
curl -X GET http://localhost:8000/customers \
  -H "Authorization: Bearer $TOKEN"

# Search by name
curl -X GET "http://localhost:8000/customers?q=Muster" \
  -H "Authorization: Bearer $TOKEN"

# Filter by ERP number
curl -X GET "http://localhost:8000/customers?erp_number=4711" \
  -H "Authorization: Bearer $TOKEN"

# Get specific customer with contacts
curl -X GET http://localhost:8000/customers/$CUSTOMER_ID \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Update Customer

```bash
curl -X PATCH http://localhost:8000/customers/$CUSTOMER_ID \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "billing_address": {
      "street": "New Street 123"
    },
    "default_currency": "CHF"
  }'
```

## Testing Import Upsert

```bash
# First import
curl -X POST http://localhost:8000/imports/customers \
  -F "file=@customers_v1.csv"

# Second import with same ERP numbers but updated names
curl -X POST http://localhost:8000/imports/customers \
  -F "file=@customers_v2.csv"

# Customers should be updated, not duplicated
```

## Testing Primary Contact Logic

```python
from src.database import SessionLocal
from src.models.customer_contact import CustomerContact

session = SessionLocal()
customer_id = "customer-uuid"

# Create first contact
contact1 = CustomerContact(
    org_id=org_id,
    customer_id=customer_id,
    email="contact1@example.com",
    is_primary=True
)
session.add(contact1)
session.commit()

# Create second contact as primary (should unset first)
contact2 = CustomerContact(
    org_id=org_id,
    customer_id=customer_id,
    email="contact2@example.com",
    is_primary=True
)
session.add(contact2)
session.commit()

# Verify only one primary
primary_count = session.query(CustomerContact).filter(
    CustomerContact.customer_id == customer_id,
    CustomerContact.is_primary == True
).count()
assert primary_count == 1
```

## Additional Resources

- **Sample CSV**: `docs/sample_customers.csv` (10 DACH customers)
- **Import Guide**: `docs/customer_import_guide.md` (complete CSV format, validation rules, troubleshooting)
- **Implementation Summary**: `specs/004-customer-management/IMPLEMENTATION_SUMMARY.md` (all files created, technical details)

## Troubleshooting

**Import fails with "Invalid currency"**: Ensure currency is in allowed list. See `docs/customer_import_guide.md` for complete list of 38 supported currencies.

**Duplicate ERP number error**: Same ERP number exists in org. Either update existing or use different number.

**Contact email not unique**: Email already exists for this customer (case-insensitive check).

**See also**: `docs/customer_import_guide.md` for complete troubleshooting guide.

## Next Steps

- Implement customer-specific pricing (future spec)
- Implement customer detection from email addresses (future spec)
- Implement customer-specific SKU mappings (future spec)
