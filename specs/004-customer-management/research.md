# Research: Customer Management

**Feature**: 004-customer-management
**Date**: 2025-12-27

## Key Decisions

### 1. JSONB for Addresses (Not Separate Tables)

**Decision**: Store billing/shipping addresses in JSONB columns, not normalized address tables.

**Rationale**:
- **Simplicity**: Avoids joins for common customer retrieval
- **Flexibility**: Address schema can vary by country without migrations
- **Performance**: Single table query vs multi-table join
- **JSONB queryability**: Can still filter/index if needed

**Schema**:
```python
class Address(BaseModel):
    street: str | None
    street2: str | None
    city: str | None
    postal_code: str | None
    state: str | None
    country: str | None  # ISO 3166-1 alpha-2
```

**References**: SSOT §5.4.3

---

### 2. CSV Import with Pandas (Upsert Pattern)

**Decision**: Use pandas for CSV parsing, upsert based on ERP customer number.

**Implementation**:
```python
import pandas as pd

def import_customers_csv(file_path: str, org_id: UUID, session: Session):
    df = pd.read_csv(file_path)

    imported, updated, failed = 0, 0, 0
    errors = []

    for idx, row in df.iterrows():
        try:
            # Validate row
            customer_data = CustomerCreate.parse_obj(row.to_dict())

            # Upsert logic
            existing = session.query(Customer).filter(
                Customer.org_id == org_id,
                Customer.erp_customer_number == customer_data.erp_customer_number
            ).first()

            if existing:
                # Update
                for key, value in customer_data.dict(exclude_unset=True).items():
                    setattr(existing, key, value)
                updated += 1
            else:
                # Insert
                new_customer = Customer(org_id=org_id, **customer_data.dict())
                session.add(new_customer)
                imported += 1

            session.commit()

        except Exception as e:
            failed += 1
            errors.append({"row": idx + 2, "error": str(e)})  # +2: header + 0-index
            session.rollback()

    return {"imported": imported, "updated": updated, "failed": failed, "errors": errors}
```

**Benefits**:
- Idempotent: Re-running same CSV produces same result
- Partial failure: Invalid rows don't block valid ones
- Error reporting: User gets specific row numbers

**References**: SSOT §8.4 (Customer import)

---

### 3. CITEXT for Email (Case-Insensitive)

**Decision**: Use PostgreSQL CITEXT type for customer_contact.email.

**Rationale**:
- Database-level case-insensitivity (email@example.com == EMAIL@example.com)
- Unique constraint works correctly across cases
- No need for application-level normalization

**Schema**:
```sql
CREATE TABLE customer_contact (
  email CITEXT NOT NULL,
  UNIQUE (customer_id, email)  -- Case-insensitive uniqueness
);
```

**References**: SSOT §5.4.4

---

### 4. Primary Contact Logic

**Decision**: Only one contact per customer can be `is_primary = true`.

**Implementation**:
```python
def set_primary_contact(session: Session, customer_id: UUID, contact_id: UUID):
    # Unset existing primary
    session.query(CustomerContact).filter(
        CustomerContact.customer_id == customer_id,
        CustomerContact.is_primary == True
    ).update({"is_primary": False})

    # Set new primary
    contact = session.query(CustomerContact).filter(
        CustomerContact.id == contact_id
    ).first()
    contact.is_primary = True

    session.commit()
```

**Use Case**: Customer detection prioritizes primary contact email.

**References**: SSOT §12 (Customer Detection)

---

### 5. ISO Code Validation

**Decision**: Validate currency (ISO 4217) and language (BCP47) codes in Pydantic.

**Implementation**:
```python
from pydantic import BaseModel, validator

VALID_CURRENCIES = ["EUR", "USD", "CHF", "GBP"]  # Subset for MVP
VALID_LANGUAGES = ["de-DE", "en-US", "fr-FR", "it-IT"]

class CustomerCreate(BaseModel):
    default_currency: str
    default_language: str

    @validator('default_currency')
    def validate_currency(cls, v):
        if v not in VALID_CURRENCIES:
            raise ValueError(f"Invalid currency: {v}")
        return v

    @validator('default_language')
    def validate_language(cls, v):
        if v not in VALID_LANGUAGES:
            raise ValueError(f"Invalid language: {v}")
        return v
```

**Benefits**: Early rejection of invalid data, prevents garbage in database.

**References**: SSOT §5.4.3

---

## Testing Strategy

### Import Tests

```python
def test_csv_import_success(db_session, test_org):
    csv_content = """
name,erp_customer_number,default_currency,default_language
Muster GmbH,4711,EUR,de-DE
Acme AG,4712,CHF,de-DE
"""
    result = import_customers_csv(io.StringIO(csv_content), test_org.id, db_session)

    assert result["imported"] == 2
    assert result["failed"] == 0

def test_csv_import_upsert(db_session, test_org):
    # First import
    import_customers_csv(csv_file_1, test_org.id, db_session)

    # Second import with same ERP number but updated name
    import_customers_csv(csv_file_2, test_org.id, db_session)

    customer = db_session.query(Customer).filter(
        Customer.erp_customer_number == "4711"
    ).first()
    assert customer.name == "Updated Name"  # Upserted

def test_csv_import_validation_errors(db_session, test_org):
    csv_content = """
name,erp_customer_number,default_currency,default_language
,4711,EUR,de-DE
Acme,4712,INVALID,de-DE
"""
    result = import_customers_csv(io.StringIO(csv_content), test_org.id, db_session)

    assert result["failed"] == 2
    assert len(result["errors"]) == 2
```

---

## Performance Considerations

### Bulk Import Optimization

For large imports (10,000+ customers):
- Use `session.bulk_insert_mappings()` instead of individual inserts
- Batch commits every 1000 records
- Disable autoflush during import

```python
customers_to_insert = []
for idx, row in df.iterrows():
    customers_to_insert.append(customer_data.dict())

    if len(customers_to_insert) >= 1000:
        session.bulk_insert_mappings(Customer, customers_to_insert)
        session.commit()
        customers_to_insert = []
```

---

## References

- SSOT §5.4.3: customer table
- SSOT §5.4.4: customer_contact table
- SSOT §8.4: Customer API
