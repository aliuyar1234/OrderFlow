"""LLM prompt templates for extraction (SSOT §7.5.3)."""

# Template for text-based PDF extraction
PDF_EXTRACT_TEXT_V1_SYSTEM = """You are an information extraction engine for B2B purchase orders.
Your job: extract a purchase order into STRICT JSON that matches the provided schema exactly.
Rules:
- Output ONLY JSON. No markdown. No explanations.
- If a field is unknown or not present, use null (do NOT invent).
- Keep original numbers as decimals. Use dot as decimal separator.
- Dates must be ISO format YYYY-MM-DD if present, else null.
- Currency must be ISO 4217 (EUR, CHF). If unclear, null.
- line_no must be 1..n sequential.
- For each line, if you cannot find customer_sku_raw and product_description, still create a line but set missing fields to null and lower confidence.
- Include per-field confidence 0..1 for required fields."""

PDF_EXTRACT_TEXT_V1_USER = """CONTEXT (do not output, only use):
- inbound_from_email: {{from_email}}
- inbound_subject: {{subject}}
- org_default_currency: {{default_currency}}
- canonical_uoms: ST,M,CM,MM,KG,G,L,ML,KAR,PAL,SET
- known_customer_numbers: {{known_customer_numbers_csv}}
- hint_examples (optional): {{hint_examples}}

TASK:
Extract the purchase order from the text below into STRICT JSON.

STRICT JSON SCHEMA (keys must match exactly):
{
  "order": {
    "external_order_number": string|null,
    "order_date": string|null,
    "currency": string|null,
    "requested_delivery_date": string|null,
    "customer_hint": {
      "name": string|null,
      "email": string|null,
      "erp_customer_number": string|null
    },
    "notes": string|null,
    "ship_to": { "company": string|null, "street": string|null, "zip": string|null, "city": string|null, "country": string|null }
  },
  "lines": [
    {
      "line_no": number,
      "customer_sku_raw": string|null,
      "product_description": string|null,
      "qty": number|null,
      "uom": string|null,
      "unit_price": number|null,
      "currency": string|null,
      "requested_delivery_date": string|null
    }
  ],
  "confidence": {
    "order": {
      "external_order_number": number,
      "order_date": number,
      "currency": number,
      "customer_hint": number
    },
    "lines": [
      { "customer_sku_raw": number, "qty": number, "uom": number, "unit_price": number }
    ],
    "overall": number
  },
  "warnings": [ { "code": string, "message": string } ],
  "extractor_version": "llm_v1"
}

PURCHASE ORDER TEXT:
<<<
{{pdf_text}}
>>>"""

# Template for vision-based PDF extraction
PDF_EXTRACT_VISION_V1_SYSTEM = """You are an information extraction engine for B2B purchase orders.
You will be given page images of a purchase order.
Extract into STRICT JSON matching the schema exactly.
Rules:
- Output ONLY JSON.
- Never invent values. Use null when unsure.
- Use ISO dates YYYY-MM-DD; currency ISO 4217.
- UoM must be one of the canonical codes if you can map it; else null.
- Provide per-field confidence 0..1."""

PDF_EXTRACT_VISION_V1_USER = """CONTEXT (do not output):
- inbound_from_email: {{from_email}}
- inbound_subject: {{subject}}
- org_default_currency: {{default_currency}}
- canonical_uoms: ST,M,CM,MM,KG,G,L,ML,KAR,PAL,SET
- known_customer_numbers: {{known_customer_numbers_csv}}
- hint_examples (optional): {{hint_examples}}

TASK:
Extract the purchase order from these page images into STRICT JSON matching the schema (same as pdf_extract_text_v1).
Return ONLY JSON.

(Images attached separately by the system: page_1.png ... page_n.png)"""

# Template for JSON repair
JSON_REPAIR_V1_SYSTEM = """You are a JSON repair tool.
You will receive invalid JSON that was intended to match a strict schema.
Return ONLY corrected JSON that:
- Is valid JSON
- Matches the schema keys exactly
- Keeps as much original content as possible
- Does not add invented values; use null if uncertain
No explanations."""

JSON_REPAIR_V1_USER = """SCHEMA (keys must match exactly): {{schema_json}}

INVALID JSON:
<<<
{{invalid_json}}
>>>

VALIDATION ERROR:
{{validation_error}}

Return ONLY corrected JSON."""


def build_text_extraction_prompt(
    pdf_text: str,
    from_email: str | None = None,
    subject: str | None = None,
    default_currency: str = "EUR",
    known_customer_numbers_csv: str = "",
    hint_examples: str = ""
) -> tuple[str, str]:
    """Build text extraction prompt from template.

    Args:
        pdf_text: Extracted PDF text
        from_email: Sender email
        subject: Email subject
        default_currency: Organization default currency
        known_customer_numbers_csv: CSV of known customer numbers
        hint_examples: JSON string of few-shot examples

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    user_prompt = PDF_EXTRACT_TEXT_V1_USER.replace("{{from_email}}", from_email or "")
    user_prompt = user_prompt.replace("{{subject}}", subject or "")
    user_prompt = user_prompt.replace("{{default_currency}}", default_currency)
    user_prompt = user_prompt.replace("{{known_customer_numbers_csv}}", known_customer_numbers_csv)
    user_prompt = user_prompt.replace("{{hint_examples}}", hint_examples)
    user_prompt = user_prompt.replace("{{pdf_text}}", pdf_text)

    return PDF_EXTRACT_TEXT_V1_SYSTEM, user_prompt


def build_vision_extraction_prompt(
    from_email: str | None = None,
    subject: str | None = None,
    default_currency: str = "EUR",
    known_customer_numbers_csv: str = "",
    hint_examples: str = ""
) -> tuple[str, str]:
    """Build vision extraction prompt from template.

    Args:
        from_email: Sender email
        subject: Email subject
        default_currency: Organization default currency
        known_customer_numbers_csv: CSV of known customer numbers
        hint_examples: JSON string of few-shot examples

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    user_prompt = PDF_EXTRACT_VISION_V1_USER.replace("{{from_email}}", from_email or "")
    user_prompt = user_prompt.replace("{{subject}}", subject or "")
    user_prompt = user_prompt.replace("{{default_currency}}", default_currency)
    user_prompt = user_prompt.replace("{{known_customer_numbers_csv}}", known_customer_numbers_csv)
    user_prompt = user_prompt.replace("{{hint_examples}}", hint_examples)

    return PDF_EXTRACT_VISION_V1_SYSTEM, user_prompt


def build_json_repair_prompt(
    invalid_json: str,
    validation_error: str,
    schema_json: str
) -> tuple[str, str]:
    """Build JSON repair prompt from template.

    Args:
        invalid_json: The invalid JSON string
        validation_error: Error message from validation
        schema_json: JSON schema string

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    user_prompt = JSON_REPAIR_V1_USER.replace("{{schema_json}}", schema_json)
    user_prompt = user_prompt.replace("{{invalid_json}}", invalid_json)
    user_prompt = user_prompt.replace("{{validation_error}}", validation_error)

    return JSON_REPAIR_V1_SYSTEM, user_prompt
