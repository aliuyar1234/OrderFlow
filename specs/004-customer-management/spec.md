# Feature Specification: Customer Management

**Feature Branch**: `004-customer-management`
**Created**: 2025-12-27
**Status**: Draft
**Module**: catalog (Customer domain)
**SSOT References**: §5.4.3 (customer table), §5.4.4 (customer_contact table), §8.4 (Customer API)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import Customer Master Data (Priority: P1)

As an INTEGRATOR, I need to import customer master data from our ERP so that OrderFlow knows about our customers and can detect them in incoming orders.

**Why this priority**: Customer data is foundational for order processing. Without customers in the system, customer detection and pricing cannot work.

**Independent Test**: Can be fully tested by uploading a CSV with customer data, verifying the import succeeds, and querying the customer list to confirm all records were created. Delivers the core customer database.

**Acceptance Scenarios**:

1. **Given** I have a CSV with customer data (name, ERP number, currency, language), **When** I POST to `/imports/customers`, **Then** all customers are created in the database
2. **Given** a customer already exists with the same ERP number, **When** I import a CSV containing updated data for that customer, **Then** the existing customer is updated (upsert behavior)
3. **Given** the CSV contains invalid data (missing required fields), **When** I import it, **Then** I receive an error report identifying the invalid rows
4. **Given** I import customers with billing and shipping addresses, **When** the import completes, **Then** addresses are stored in the address_json fields

---

### User Story 2 - Manage Customer Contacts (Priority: P1)

As an ADMIN user, I need to add and manage contact persons for customers so that the system can match incoming order emails to the correct customer.

**Why this priority**: Email-based customer detection relies on contact email addresses. Without contacts, automatic customer detection cannot work.

**Independent Test**: Can be tested by creating a customer, adding multiple contacts with different email addresses, and verifying that incoming messages from those emails are matched to the customer.

**Acceptance Scenarios**:

1. **Given** a customer exists, **When** I add a contact with email and name, **Then** the contact is associated with the customer
2. **Given** a customer has multiple contacts, **When** I mark one as primary, **Then** it becomes the primary contact and any previously primary contact is unmarked
3. **Given** a contact email already exists for a customer, **When** I attempt to add it again, **Then** I receive a unique constraint error
4. **Given** I import a customer CSV with contact information, **When** the import processes, **Then** contacts are created and linked to their customers
5. **Given** a customer has contacts, **When** I delete a contact, **Then** it is removed without affecting the customer record

---

### User Story 3 - View and Search Customers (Priority: P2)

As an OPS user, I need to view and search the customer list so that I can manually select the correct customer when reviewing draft orders.

**Why this priority**: While automatic detection is the goal, manual customer selection is essential when detection fails or is ambiguous.

**Independent Test**: Can be tested by creating multiple customers, using the search/filter API with different criteria, and verifying the results match expectations.

**Acceptance Scenarios**:

1. **Given** multiple customers exist, **When** I GET `/customers`, **Then** I receive a paginated list of customers
2. **Given** I search for customers by name, **When** I GET `/customers?q=Muster`, **Then** I receive customers whose names contain "Muster"
3. **Given** I filter by erp_customer_number, **When** I GET `/customers?erp_number=4711`, **Then** I receive only the customer with that ERP customer number
4. **Given** I request a specific customer by ID, **When** I GET `/customers/{id}`, **Then** I receive the full customer details including contacts
5. **Given** customers exist in multiple orgs, **When** I query as Org A, **Then** I only see Org A's customers

---

### User Story 4 - Update Customer Information (Priority: P2)

As an ADMIN, I need to update customer information (addresses, default currency, contacts) so that I can keep the data current without reimporting everything.

**Why this priority**: Customer data changes over time. While bulk imports handle initial setup, individual updates are needed for maintenance.

**Independent Test**: Can be tested by creating a customer, updating specific fields via PATCH endpoint, and verifying only those fields changed while others remain unchanged.

**Acceptance Scenarios**:

1. **Given** a customer exists, **When** I PATCH `/customers/{id}` with updated billing address, **Then** the billing address is updated while other fields remain unchanged
2. **Given** a customer exists, **When** I update the default currency, **Then** new draft orders for that customer default to the new currency
3. **Given** a customer's ERP number changes, **When** I update it via API, **Then** the new ERP number is saved and exports use the new value
4. **Given** I update a customer with invalid data (empty name), **When** I submit it, **Then** I receive a validation error

---

### Edge Cases

- If a CSV contains duplicate ERP customer numbers, the last occurrence wins (later row overwrites earlier row). System MUST log warning with row numbers for duplicate keys found.
- How does the system handle customers with no ERP customer number (manual customers)?
- What happens when a contact email domain changes (customer changed email providers)?
- How does the system handle international characters in customer names and addresses?
- What happens when attempting to delete a customer that has associated draft orders?
- How does the system handle very large customer imports (10,000+ records)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide API to import customers from CSV files
- **FR-002**: System MUST support upsert behavior for customer imports (update if ERP number exists, insert if new)
- **FR-003**: System MUST store customer billing and shipping addresses as JSONB
- **FR-004**: System MUST enforce unique erp_customer_number per org (but allow NULL)
- **FR-005**: System MUST support multiple contacts per customer with email addresses
- **FR-006**: System MUST enforce unique email addresses per customer (case-insensitive)
- **FR-007**: System MUST allow marking one contact as primary per customer
- **FR-008**: System MUST provide API to create, read, update customers (ADMIN/INTEGRATOR roles)
- **FR-009**: System MUST provide API to manage customer contacts
- **FR-010**: System MUST support search/filter on customer name and erp_customer_number
- **FR-011**: System MUST validate default_currency against ISO 4217 codes
- **FR-012**: System MUST validate default_language against BCP47 codes
- **FR-013**: If a CSV contains duplicate ERP customer numbers, the last occurrence wins (later row overwrites earlier row). System MUST log warning with row numbers for duplicate keys found.

### Key Entities

- **Customer**: Represents a business customer (buyer). Each customer belongs to one organization and may have an erp_customer_number for integration. Customers have default currency/language settings and addresses stored as JSON.

- **CustomerContact**: Represents a contact person at a customer organization. Each contact has an email address used for customer detection. One contact per customer can be marked as primary.

### Technical Constraints

- **TC-001**: Email addresses MUST use CITEXT type for case-insensitive comparison
- **TC-002**: Addresses MUST be stored as JSONB, not separate tables (MVP simplicity)
- **TC-003**: erp_customer_number can be NULL (for manually created customers)
- **TC-004**: Customer name and default_currency are required fields
- **TC-005**: Contact email must be a valid email format (validated by Pydantic)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Customer import processes 1000 records in under 30 seconds
- **SC-002**: Customer search returns results in under 200ms for typical queries
- **SC-003**: 100% of imported customers with valid data are successfully created
- **SC-004**: Zero duplicate customer_contact emails per customer (enforced by constraint)
- **SC-005**: Customer API responds in under 100ms for single customer retrieval (P95)

### Data Quality

- **DQ-001**: Customer names support full Unicode (international characters)
- **DQ-002**: Address JSON supports all fields needed for shipping (street, city, postal code, country, etc.)
- **DQ-003**: Email normalization is consistent (lowercase, trimmed)
- **DQ-004**: ISO currency codes are validated (reject invalid codes)

## Dependencies

- **Depends on**: 001-platform-foundation (database, org table)
- **Depends on**: 002-auth-rbac (role enforcement)
- **Depends on**: 003-tenancy-isolation (org_id scoping)
- **Dependency reason**: Customer data is multi-tenant and requires authentication/authorization

## Implementation Notes

### Customer Table Schema (SSOT §5.4.3)

```sql
CREATE TABLE customer (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  name TEXT NOT NULL,
  erp_customer_number TEXT,
  default_currency TEXT NOT NULL,  -- ISO 4217
  default_language TEXT NOT NULL,  -- BCP47
  billing_address_json JSONB,
  shipping_address_json JSONB,
  metadata_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, erp_customer_number) WHERE erp_customer_number IS NOT NULL
);

CREATE INDEX idx_customer_org_name ON customer(org_id, name);
CREATE INDEX idx_customer_org_erp ON customer(org_id, erp_customer_number);
```

### Customer Contact Table Schema (SSOT §5.4.4)

```sql
CREATE TABLE customer_contact (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  customer_id UUID NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
  email CITEXT NOT NULL,
  name TEXT,
  is_primary BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (customer_id, email)
);

CREATE INDEX idx_customer_contact_org_customer ON customer_contact(org_id, customer_id);
CREATE INDEX idx_customer_contact_email ON customer_contact(org_id, email);
```

### Address JSON Schema

```python
from pydantic import BaseModel
from typing import Optional

class Address(BaseModel):
    street: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None  # ISO 3166-1 alpha-2

class Customer(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    erp_customer_number: Optional[str] = None
    default_currency: str  # ISO 4217
    default_language: str  # BCP47
    billing_address: Optional[Address] = None
    shipping_address: Optional[Address] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
```

### API Endpoints (SSOT §8.4)

#### GET `/customers`

Query parameters:
- `q`: Search query (name or erp_customer_number)
- `erp_number`: Filter by exact erp_customer_number
- `limit`: Page size (default 50)
- `cursor`: Pagination cursor

```json
// Response 200
{
  "items": [
    {
      "id": "uuid",
      "name": "Muster GmbH",
      "erp_customer_number": "4711",
      "default_currency": "EUR",
      "default_language": "de-DE",
      "billing_address": {
        "street": "Musterstraße 1",
        "city": "München",
        "postal_code": "80331",
        "country": "DE"
      },
      "contact_count": 3
    }
  ],
  "next_cursor": "uuid"
}
```

#### GET `/customers/{id}`

```json
// Response 200
{
  "id": "uuid",
  "name": "Muster GmbH",
  "erp_customer_number": "4711",
  "default_currency": "EUR",
  "default_language": "de-DE",
  "billing_address": { /* ... */ },
  "shipping_address": { /* ... */ },
  "contacts": [
    {
      "id": "uuid",
      "email": "einkauf@muster.de",
      "name": "Max Mustermann",
      "is_primary": true
    }
  ],
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

#### POST `/customers`

Requires ADMIN or INTEGRATOR role.

```json
// Request
{
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
}

// Response 201
{
  "id": "uuid",
  /* ... full customer object ... */
}
```

#### PATCH `/customers/{id}`

Requires ADMIN or INTEGRATOR role.

```json
// Request
{
  "billing_address": {
    "street": "New Street 123"
  }
}

// Response 200
{ /* full updated customer object */ }
```

#### POST `/customers/{id}/contacts`

```json
// Request
{
  "email": "einkauf@muster.de",
  "name": "Max Mustermann",
  "is_primary": true
}

// Response 201
{
  "id": "uuid",
  "email": "einkauf@muster.de",
  "name": "Max Mustermann",
  "is_primary": true
}
```

#### DELETE `/customers/{customer_id}/contacts/{contact_id}`

Requires ADMIN or INTEGRATOR role.

```json
// Response 204 No Content
```

### Customer Import CSV Format

```csv
name,erp_customer_number,default_currency,default_language,billing_street,billing_city,billing_postal_code,billing_country,contact_email,contact_name,contact_is_primary
"Muster GmbH",4711,EUR,de-DE,"Musterstraße 1",München,80331,DE,einkauf@muster.de,"Max Mustermann",true
```

#### POST `/imports/customers`

Multipart form upload with CSV file.

```json
// Response 200
{
  "imported": 42,
  "updated": 8,
  "failed": 0,
  "errors": []
}

// Response 200 (with errors)
{
  "imported": 40,
  "updated": 8,
  "failed": 2,
  "errors": [
    {
      "row": 5,
      "error": "Invalid currency code: USD123"
    },
    {
      "row": 12,
      "error": "Missing required field: name"
    }
  ]
}
```

### Primary Contact Logic

When setting `is_primary = true` on a contact:
1. Find any existing primary contact for the customer
2. Set existing primary to `is_primary = false`
3. Set new contact to `is_primary = true`
4. Execute in transaction to ensure atomicity

### Validation Rules

- **Customer Name**: Required, 1-500 characters, Unicode support
- **erp_customer_number**: Optional, 1-100 characters, alphanumeric + hyphens
- **Default Currency**: Required, valid ISO 4217 code (EUR, USD, CHF, etc.)
- **Default Language**: Required, valid BCP47 code (de-DE, en-US, fr-FR, etc.)
- **Contact Email**: Required, valid email format, case-insensitive unique per customer
- **Contact Name**: Optional, 1-200 characters

## Out of Scope

- Customer pricing (covered in later spec)
- Customer price lists / tier pricing (covered in later spec)
- Customer credit limits
- Customer payment terms
- Customer-specific SKU mappings (covered in matching spec)
- Customer hierarchy (parent/subsidiary relationships)
- Customer deduplication / merge functionality
- Customer deletion (only disable/archive in MVP)
- Contact phone numbers (email only for MVP)
- Contact roles (all contacts are generic for MVP)

## Testing Strategy

### Unit Tests
- Customer model validation
- Address JSON schema validation
- Currency/language code validation
- Contact email normalization
- Primary contact toggle logic

### Integration Tests
- Customer CRUD operations via API
- Customer contact CRUD operations
- Customer import from CSV (success cases)
- Customer import error handling (validation failures)
- Upsert behavior (update existing customer)
- Search and filter functionality
- Pagination
- Multi-tenant isolation (cannot access other org's customers)
- Unique constraints (ERP number, contact email)
- Primary contact uniqueness (only one primary per customer)

### Import Tests
- Large import (1000+ customers)
- Import with various edge cases (Unicode names, special characters)
- Import with missing optional fields
- Import with invalid data (validation errors)
- Import with duplicate erp_customer_number (within org, across orgs)
- Concurrent imports from different orgs

### Performance Tests
- Customer list query with 10,000 customers (<200ms)
- Customer search query (<200ms)
- Import of 1000 customers (<30 seconds)
- Single customer retrieval (<100ms)

### Data Integrity Tests
- Cannot create duplicate erp_customer_number in same org
- Can create same erp_customer_number in different orgs
- Cannot create duplicate contact emails for same customer
- Can create same email for different customers
- Primary contact constraint (max one per customer)
- Cascade delete of contacts when customer is deleted
