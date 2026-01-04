# Catalog API Documentation

## Overview

The Catalog API provides endpoints for managing products and units of measure (UoM). It supports CRUD operations, CSV import, and advanced search capabilities.

**Base Path**: `/products`

**Authentication**: All endpoints require authentication. Some endpoints require specific roles (ADMIN, INTEGRATOR, OPS).

## Endpoints

### Product Management

#### Create Product
```http
POST /products
```

**Required Roles**: ADMIN, INTEGRATOR

**Request Body**:
```json
{
  "internal_sku": "PROD-001",
  "name": "Sample Product",
  "description": "Product description",
  "base_uom": "ST",
  "uom_conversions_json": {
    "KAR": {"to_base": 12},
    "PAL": {"to_base": 480}
  },
  "active": true,
  "attributes_json": {
    "manufacturer": "ACME Corp",
    "ean": "1234567890123",
    "category": "Electronics"
  }
}
```

**Response**: `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "org_id": "660e8400-e29b-41d4-a716-446655440000",
  "internal_sku": "PROD-001",
  "name": "Sample Product",
  "description": "Product description",
  "base_uom": "ST",
  "uom_conversions_json": {
    "KAR": {"to_base": 12},
    "PAL": {"to_base": 480}
  },
  "active": true,
  "attributes_json": {
    "manufacturer": "ACME Corp",
    "ean": "1234567890123",
    "category": "Electronics"
  },
  "updated_source_at": "2026-01-04T14:00:00Z",
  "created_at": "2026-01-04T14:00:00Z",
  "updated_at": "2026-01-04T14:00:00Z"
}
```

**Errors**:
- `400 Bad Request`: Product with SKU already exists
- `400 Bad Request`: Invalid base_uom (must be one of: ST, M, CM, MM, KG, G, L, ML, KAR, PAL, SET)

---

#### List Products
```http
GET /products?search={term}&active={bool}&limit={int}&offset={int}
```

**Required Roles**: Any authenticated user

**Query Parameters**:
- `search` (optional): Search term for SKU, name, or description
- `active` (optional): Filter by active status (true/false)
- `limit` (optional, default: 50, max: 100): Number of results per page
- `offset` (optional, default: 0): Number of results to skip

**Response**: `200 OK`
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "org_id": "660e8400-e29b-41d4-a716-446655440000",
    "internal_sku": "PROD-001",
    "name": "Sample Product",
    "description": "Product description",
    "base_uom": "ST",
    "uom_conversions_json": {...},
    "active": true,
    "attributes_json": {...},
    "updated_source_at": "2026-01-04T14:00:00Z",
    "created_at": "2026-01-04T14:00:00Z",
    "updated_at": "2026-01-04T14:00:00Z"
  }
]
```

---

#### Get Product by ID
```http
GET /products/{product_id}
```

**Required Roles**: Any authenticated user

**Response**: `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "org_id": "660e8400-e29b-41d4-a716-446655440000",
  "internal_sku": "PROD-001",
  "name": "Sample Product",
  "description": "Product description",
  "base_uom": "ST",
  "uom_conversions_json": {...},
  "active": true,
  "attributes_json": {...},
  "updated_source_at": "2026-01-04T14:00:00Z",
  "created_at": "2026-01-04T14:00:00Z",
  "updated_at": "2026-01-04T14:00:00Z"
}
```

**Errors**:
- `404 Not Found`: Product not found or belongs to different organization

---

#### Update Product
```http
PATCH /products/{product_id}
```

**Required Roles**: ADMIN, INTEGRATOR, OPS

**Request Body** (all fields optional):
```json
{
  "name": "Updated Product Name",
  "description": "Updated description",
  "base_uom": "KG",
  "uom_conversions_json": {...},
  "active": false,
  "attributes_json": {...}
}
```

**Response**: `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "org_id": "660e8400-e29b-41d4-a716-446655440000",
  "internal_sku": "PROD-001",
  "name": "Updated Product Name",
  ...
}
```

**Errors**:
- `404 Not Found`: Product not found or belongs to different organization

---

### Product Import

#### Import Products from CSV
```http
POST /products/import
```

**Required Roles**: ADMIN, INTEGRATOR

**Request**: `multipart/form-data`
- `file`: CSV file with products

**CSV Format**:
- **Required columns**: `internal_sku`, `name`, `base_uom`
- **Optional columns**: `description`, `manufacturer`, `ean`, `category`, `uom_conversions`

**CSV Example**:
```csv
internal_sku,name,base_uom,description,manufacturer,ean,category,uom_conversions
PROD-001,Product 1,ST,Description,ACME,1234567890123,Electronics,"{""KAR"":{""to_base"":12}}"
PROD-002,Product 2,KG,Description,Beta,9876543210987,Materials,
```

**Response**: `200 OK`
```json
{
  "total_rows": 100,
  "imported_count": 95,
  "error_count": 5,
  "errors": [
    {
      "row": 15,
      "sku": "PROD-015",
      "error": "Invalid base_uom: PIECES. Must be one of: CM, G, KAR, KG, L, M, ML, MM, PAL, SET, ST"
    },
    {
      "row": 23,
      "sku": "",
      "error": "internal_sku is required"
    }
  ]
}
```

**Behavior**:
- **Upsert**: If a product with the same `internal_sku` exists, it will be updated. Otherwise, a new product is created.
- **Encoding Detection**: Automatically detects CSV encoding (UTF-8, Windows-1252, etc.)
- **Error Handling**: Continues processing even if some rows fail. Returns detailed error information.

**Errors**:
- `400 Bad Request`: File is not a CSV

---

### Unit of Measure Management

#### Create Unit of Measure
```http
POST /products/uom
```

**Required Roles**: ADMIN, INTEGRATOR

**Request Body**:
```json
{
  "code": "KAR",
  "name": "Karton",
  "conversion_factor": 12.0
}
```

**Response**: `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "org_id": "660e8400-e29b-41d4-a716-446655440000",
  "code": "KAR",
  "name": "Karton",
  "conversion_factor": 12.0,
  "created_at": "2026-01-04T14:00:00Z",
  "updated_at": "2026-01-04T14:00:00Z"
}
```

**Errors**:
- `400 Bad Request`: Unit of measure with code already exists

---

#### List Units of Measure
```http
GET /products/uom
```

**Required Roles**: Any authenticated user

**Response**: `200 OK`
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "org_id": "660e8400-e29b-41d4-a716-446655440000",
    "code": "KAR",
    "name": "Karton",
    "conversion_factor": 12.0,
    "created_at": "2026-01-04T14:00:00Z",
    "updated_at": "2026-01-04T14:00:00Z"
  }
]
```

---

## Canonical UoM Codes

Products must use one of the following canonical UoM codes for `base_uom`:

- `ST` - Stück (Piece)
- `M` - Meter
- `CM` - Centimeter
- `MM` - Millimeter
- `KG` - Kilogram
- `G` - Gram
- `L` - Liter
- `ML` - Milliliter
- `KAR` - Karton (Carton)
- `PAL` - Palette (Pallet)
- `SET` - Set

## UoM Conversions

Products can define conversions from pack units to base units using the `uom_conversions_json` field:

```json
{
  "KAR": {"to_base": 12},
  "PAL": {"to_base": 480}
}
```

This example means:
- 1 KAR (Karton) = 12 base units (ST)
- 1 PAL (Palette) = 480 base units (ST)

## Multi-Tenant Isolation

All product and UoM data is isolated by `org_id`. Users can only access data belonging to their organization. Attempting to access data from another organization returns a `404 Not Found` error (not `403 Forbidden`) to prevent information disclosure.

## Search Performance

The API includes optimized search capabilities:
- **Full-text search**: GIN index on name and description
- **Exact match**: Indexed searches on internal_sku
- **Attribute search**: GIN index on JSONB attributes
- **Response time**: < 200ms for 10k product catalog

## Error Handling

All endpoints return standard HTTP status codes:
- `200 OK`: Successful GET/PATCH
- `201 Created`: Successful POST
- `400 Bad Request`: Validation error
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
