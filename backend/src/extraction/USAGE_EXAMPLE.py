"""Usage example for LLM extractor.

This demonstrates how to integrate the LLM extractor into the
document processing pipeline.
"""

import os
from typing import Any

# Example usage (when fully integrated)
def example_text_extraction():
    """Example: Extract order from text-based PDF."""
    from ai.providers.openai_provider import OpenAIProvider
    from extraction.extractors.llm_extractor import LLMExtractor
    from extraction.decision_logic import decide_extraction_method

    # 1. Initialize provider
    provider = OpenAIProvider(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_text="gpt-4o-mini",
        model_vision="gpt-4o",
        timeout_seconds=40,
    )

    # 2. Initialize extractor
    extractor = LLMExtractor(
        llm_provider=provider,
        max_lines=500,
        max_qty=1_000_000,
    )

    # 3. Prepare context
    pdf_text = """
    BESTELLUNG / PURCHASE ORDER

    Bestellnummer: PO-2025-001
    Datum: 2025-01-04

    Lieferadresse:
    Musterfirma GmbH
    Musterstraße 123
    12345 Musterstadt

    Pos  Artikelnr.      Bezeichnung              Menge  Einh.  Preis
    1    ABC-123         Kabel NYM-J 3x1,5       100    M      1.23
    2    DEF-456         Schalter 2-polig        50     ST     2.45
    3    GHI-789         Steckdose IP44           25     ST     3.67
    """

    context = {
        "from_email": "einkauf@customer.de",
        "subject": "Bestellung PO-2025-001",
        "default_currency": "EUR",
        "known_customer_numbers_csv": "CUST-001,CUST-002",
        "hint_examples": "",  # Few-shot examples if available
    }

    # 4. Extract
    result = extractor.extract_from_text(
        pdf_text=pdf_text,
        context=context,
        source_text=pdf_text,
        page_count=1,
    )

    # 5. Process result
    if result["status"] == "SUCCEEDED":
        output = result["output"]
        print(f"✓ Extraction succeeded")
        print(f"  Order Number: {output.order.external_order_number}")
        print(f"  Lines: {len(output.lines)}")
        print(f"  Overall Confidence: {output.confidence.overall:.2f}")

        for line in output.lines:
            print(f"  Line {line.line_no}: {line.customer_sku_raw} - {line.qty} {line.uom}")

        if output.warnings:
            print(f"  Warnings: {len(output.warnings)}")
            for warning in output.warnings:
                print(f"    - {warning.code}: {warning.message}")

        # Access LLM result metadata
        llm_result = result["llm_result"]
        print(f"\n  LLM Metadata:")
        print(f"    Model: {llm_result.model}")
        print(f"    Tokens In: {llm_result.tokens_in}")
        print(f"    Tokens Out: {llm_result.tokens_out}")
        print(f"    Latency: {llm_result.latency_ms}ms")
        print(f"    Cost: {llm_result.cost_micros} micros")

    else:
        error = result["error"]
        print(f"✗ Extraction failed: {error['code']}")
        print(f"  Message: {error['message']}")


def example_vision_extraction():
    """Example: Extract order from scanned PDF images."""
    from ai.providers.openai_provider import OpenAIProvider
    from extraction.extractors.llm_extractor import LLMExtractor

    # 1. Initialize
    provider = OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
    extractor = LLMExtractor(llm_provider=provider)

    # 2. Convert PDF pages to images (using pdfplumber + Pillow)
    # This would typically be done in document processing pipeline
    images = []  # List of PNG bytes
    # with pdfplumber.open(pdf_path) as pdf:
    #     for page in pdf.pages[:5]:  # Max 5 pages
    #         img = page.to_image(resolution=300)
    #         img_bytes = io.BytesIO()
    #         img.save(img_bytes, format='PNG')
    #         images.append(img_bytes.getvalue())

    # 3. Context
    context = {
        "from_email": "einkauf@customer.de",
        "subject": "Order",
        "default_currency": "EUR",
        "known_customer_numbers_csv": "",
        "hint_examples": "",
    }

    # 4. Extract
    result = extractor.extract_from_images(
        images=images,
        context=context,
        source_text="",  # OCR text if available
        page_count=len(images),
    )

    # 5. Process result (same as text extraction)
    if result["status"] == "SUCCEEDED":
        print(f"✓ Vision extraction succeeded")
    else:
        print(f"✗ Vision extraction failed")


def example_decision_logic():
    """Example: Decide which extraction method to use."""
    from extraction.decision_logic import (
        decide_extraction_method,
        should_trigger_llm_fallback,
        check_budget_gate,
        estimate_llm_cost,
    )

    # Scenario 1: Scanned PDF (low text coverage)
    method = decide_extraction_method(
        text_coverage_ratio=0.08,  # 8% text coverage
        page_count=3,
        rule_based_confidence=None,
    )
    print(f"Scanned PDF → {method}")  # llm_vision

    # Scenario 2: Text PDF with low rule-based confidence
    method = decide_extraction_method(
        text_coverage_ratio=0.85,  # Good text coverage
        page_count=2,
        rule_based_confidence=0.45,  # Low confidence
    )
    print(f"Low confidence text PDF → {method}")  # llm_text

    # Scenario 3: Text PDF with good rule-based confidence
    method = decide_extraction_method(
        text_coverage_ratio=0.90,
        page_count=1,
        rule_based_confidence=0.85,  # High confidence
    )
    print(f"High confidence text PDF → {method}")  # rule_based

    # Check if fallback needed
    should_fallback = should_trigger_llm_fallback(
        rule_based_confidence=0.45,
        lines_count=10,
    )
    print(f"Should fallback to LLM: {should_fallback}")  # True

    # Check budget gate
    is_allowed, reason = check_budget_gate(
        org_id="org-123",
        daily_budget_micros=100_000,  # 0.10 EUR
        used_micros=50_000,  # 0.05 EUR used
        estimated_cost_micros=60_000,  # 0.06 EUR estimated
    )
    print(f"Budget gate: allowed={is_allowed}, reason={reason}")

    # Estimate costs
    text_cost = estimate_llm_cost(
        method="llm_text",
        text_length=5000,
        page_count=0,
    )
    print(f"Estimated text LLM cost: {text_cost} micros")

    vision_cost = estimate_llm_cost(
        method="llm_vision",
        text_length=0,
        page_count=3,
    )
    print(f"Estimated vision LLM cost: {vision_cost} micros")


def example_hallucination_guards():
    """Example: Apply hallucination guards."""
    from extraction.hallucination_guards import apply_hallucination_guards

    # Mock extraction output
    extraction_output = {
        "order": {
            "external_order_number": "PO-123",
            "order_date": "2025-01-04",
            "currency": "EUR",
        },
        "lines": [
            {
                "line_no": 1,
                "customer_sku_raw": "ABC-123",
                "product_description": "Kabel NYM-J 3x1,5",
                "qty": 100,
                "uom": "M",
                "unit_price": 1.23,
            },
            {
                "line_no": 2,
                "customer_sku_raw": "FAKE-999",  # Not in source
                "product_description": "Fake Product",
                "qty": 9999999,  # Exceeds max_qty
                "uom": "ST",
            },
        ],
        "confidence": {
            "order": {},
            "lines": [
                {"customer_sku_raw": 0.9, "qty": 0.9, "uom": 0.9, "unit_price": 0.9},
                {"customer_sku_raw": 0.9, "qty": 0.9, "uom": 0.9, "unit_price": 0.0},
            ],
            "overall": 0.85,
        },
        "warnings": [],
    }

    source_text = """
    Pos  Artikelnr.  Bezeichnung          Menge
    1    ABC-123     Kabel NYM-J 3x1,5   100
    """

    # Apply guards
    guarded_output = apply_hallucination_guards(
        extraction_output=extraction_output,
        source_text=source_text,
        page_count=1,
        max_qty=1_000_000,
    )

    print(f"Warnings after guards: {len(guarded_output['warnings'])}")
    for warning in guarded_output["warnings"]:
        print(f"  - {warning['code']}: {warning['message']}")

    print(f"Overall confidence: {guarded_output['confidence']['overall']:.2f}")


def example_layout_fingerprinting():
    """Example: Calculate layout fingerprint."""
    from extraction.layout_fingerprint import (
        calculate_layout_fingerprint,
        extract_snippet_for_feedback,
    )

    pdf_text = """
    PURCHASE ORDER

    Order No: PO-123
    Date: 2025-01-04

    Pos  SKU      Description    Qty
    1    ABC-1    Product A      10
    2    DEF-2    Product B      20
    """

    fingerprint = calculate_layout_fingerprint(
        page_count=1,
        text=pdf_text,
        has_tables=True,
    )

    print(f"Layout fingerprint: {fingerprint}")

    # Extract snippet for feedback
    snippet = extract_snippet_for_feedback(pdf_text, max_length=1500)
    print(f"Snippet length: {len(snippet)} chars")


def example_uom_normalization():
    """Example: Normalize UoM codes."""
    from extraction.uom_normalization import (
        normalize_uom,
        is_uom_compatible,
    )

    # Normalize variations
    print(f"STK → {normalize_uom('STK')}")  # ST
    print(f"stück → {normalize_uom('stück')}")  # ST
    print(f"METER → {normalize_uom('METER')}")  # M
    print(f"KILO → {normalize_uom('KILO')}")  # KG

    # Check compatibility
    print(f"M compatible with CM: {is_uom_compatible('M', 'CM')}")  # True
    print(f"KG compatible with G: {is_uom_compatible('KG', 'G')}")  # True
    print(f"M compatible with KG: {is_uom_compatible('M', 'KG')}")  # False


if __name__ == "__main__":
    print("=== LLM Extractor Usage Examples ===\n")

    print("1. Decision Logic:")
    example_decision_logic()

    print("\n2. Hallucination Guards:")
    example_hallucination_guards()

    print("\n3. Layout Fingerprinting:")
    example_layout_fingerprinting()

    print("\n4. UoM Normalization:")
    example_uom_normalization()

    print("\n=== For full extraction examples, set OPENAI_API_KEY ===")
    # Uncomment when API key is available:
    # example_text_extraction()
    # example_vision_extraction()
