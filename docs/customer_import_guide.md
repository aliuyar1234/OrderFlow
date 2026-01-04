# Customer Import Guide

This guide explains how to import customer master data into OrderFlow using CSV files.

## CSV Format

The customer import CSV must include the following columns:

### Required Columns

- **name**: Customer name (1-500 characters, Unicode supported)
- **default_currency**: ISO 4217 currency code (e.g., EUR, USD, CHF)
- **default_language**: BCP47 language code (e.g., de-DE, en-US, fr-FR)

### Optional Columns

- **erp_customer_number**: ERP customer number (unique per organization)
- **email**: Customer email address
- **notes**: Additional notes about the customer

#### Billing Address Columns

- **billing_street**: Street address line 1
- **billing_street2**: Street address line 2
- **billing_city**: City name
- **billing_postal_code**: Postal/ZIP code
- **billing_state**: State/Province
- **billing_country**: ISO 3166-1 alpha-2 country code (e.g., DE, AT, CH)

#### Shipping Address Columns

- **shipping_street**: Street address line 1
- **shipping_street2**: Street address line 2
- **shipping_city**: City name
- **shipping_postal_code**: Postal/ZIP code
- **shipping_state**: State/Province
- **shipping_country**: ISO 3166-1 alpha-2 country code

#### Contact Person Columns

- **contact_email**: Contact person's email address
- **contact_name**: Contact person's name
- **contact_phone**: Contact person's phone number
- **contact_is_primary**: Whether this is the primary contact (true/false)

## Supported Currency Codes

EUR, USD, CHF, GBP, JPY, CAD, AUD, NZD, SEK, NOK, DKK, PLN, CZK, HUF, RON, BGN, HRK, RSD, TRY, RUB, UAH, CNY, INR, BRL, MXN, ZAR, SGD, HKD, KRW, THB, IDR, MYR, PHP, VND, AED, SAR, ILS, EGP

## Supported Language Codes

de-DE, de-AT, de-CH, en-US, en-GB, fr-FR, fr-CH, it-IT, it-CH, es-ES, pt-PT, pt-BR, nl-NL, pl-PL, cs-CZ, sk-SK, hu-HU, ro-RO, bg-BG, hr-HR, sr-RS, sl-SI, sv-SE, da-DK, no-NO, fi-FI, ru-RU, uk-UA, tr-TR, el-GR, zh-CN, zh-TW, ja-JP, ko-KR, ar-SA, he-IL, th-TH, vi-VN, id-ID, ms-MY, hi-IN

## Example CSV

See `docs/sample_customers.csv` for a complete example with 10 German-speaking DACH region customers.

## Import Behavior

### Upsert Logic

The import uses **upsert** logic based on `erp_customer_number`:

- If a customer with the same `erp_customer_number` already exists in your organization, the existing customer will be **updated**
- If no matching `erp_customer_number` exists, a **new customer** will be **created**
- Customers without `erp_customer_number` are always created as new records

### Duplicate Handling

If your CSV contains duplicate `erp_customer_number` values:
- The **last occurrence wins** (later rows overwrite earlier rows)
- A warning is logged with the row numbers of duplicates
- This is by design to allow intentional overwrites during import preparation

### Contact Handling

If `contact_email` is provided:
- The contact will be created or updated for the customer
- If `contact_is_primary` is true, any existing primary contact will be unmarked
- Contact emails are case-insensitive and must be unique per customer

## Using the Import API

### Prerequisites

You must have either **ADMIN** or **INTEGRATOR** role to import customers.

### API Endpoint

```
POST /customers/imports/customers
```

### Request

Send a multipart form upload with the CSV file:

```bash
curl -X POST "https://your-orderflow-instance.com/customers/imports/customers" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@customers.csv"
```

### Response

The API returns an `ImportResult` with:

```json
{
  "imported": 42,
  "updated": 8,
  "failed": 0,
  "errors": []
}
```

#### Fields

- **imported**: Number of new customers created
- **updated**: Number of existing customers updated
- **failed**: Number of rows that failed validation
- **errors**: Array of error objects with `row` number and `error` message

### Error Response Example

```json
{
  "imported": 40,
  "updated": 8,
  "failed": 2,
  "errors": [
    {
      "row": 5,
      "error": "Invalid currency code 'USD123'"
    },
    {
      "row": 12,
      "error": "Missing required field: name"
    }
  ]
}
```

## Validation Rules

- **Name**: Cannot be empty
- **Currency**: Must be a valid ISO 4217 code (see list above)
- **Language**: Must be a valid BCP47 code (see list above)
- **Email**: Must be valid email format
- **ERP Number**: Must be unique per organization (if provided)

## Performance

- Imports of 1000 customers should complete in under 30 seconds
- Large imports are processed in a single database transaction
- If any database error occurs, the entire import is rolled back

## Best Practices

1. **Validate your CSV** before importing using a spreadsheet application
2. **Test with a small sample** first (5-10 rows)
3. **Use UTF-8 encoding** for international characters
4. **Include ERP numbers** to enable updates on subsequent imports
5. **Set one primary contact** per customer for email-based order detection
6. **Review the error report** if any rows fail validation

## Troubleshooting

### Import fails with "Invalid currency code"

- Check that your currency codes are uppercase 3-letter ISO 4217 codes
- Refer to the supported currency list above
- Common mistake: Using currency symbols (€, $) instead of codes (EUR, USD)

### Import fails with "Missing required field"

- Ensure `name`, `default_currency`, and `default_language` are present in every row
- Check for empty cells in these columns

### Duplicate ERP number error

- If updating existing customers, ensure each ERP number appears only once in your CSV
- Check for accidental duplicates using spreadsheet sorting

### Unicode characters not importing correctly

- Save your CSV with UTF-8 encoding
- Avoid using Excel's default CSV export (use "CSV UTF-8" instead)

## Router Registration

To enable the customer endpoints in your FastAPI application, add the router to your main app:

```python
from src.customers.router import router as customers_router

app.include_router(customers_router)
```

The router will be available at `/customers` with all CRUD and import endpoints.
