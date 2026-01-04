"""Embedding Text Generator - Generate canonical text for embedding.

Provides deterministic text generation from product and query data for embedding.
Text format ensures consistency and enables deduplication via text_hash.

SSOT Reference: §7.7.3 (Canonical Embedding Text)
"""

import json
import hashlib
from typing import Optional


def generate_product_embedding_text(
    internal_sku: str,
    name: str,
    description: Optional[str] = None,
    base_uom: Optional[str] = None,
    attributes_json: Optional[dict] = None,
    uom_conversions_json: Optional[dict] = None,
) -> str:
    """Generate canonical embedding text for a product.

    SSOT Reference: §7.7.3 - Format:
        SKU: {internal_sku}
        NAME: {name}
        DESC: {description}
        ATTR: {manufacturer};{ean};{category}
        UOM: base={base_uom}; conv={uom_conversions_json}

    Args:
        internal_sku: Product internal SKU
        name: Product name
        description: Product description (optional)
        base_uom: Base unit of measure (optional)
        attributes_json: Product attributes dict (optional)
        uom_conversions_json: UoM conversions dict (optional)

    Returns:
        Canonical text string for embedding

    Example:
        >>> generate_product_embedding_text(
        ...     internal_sku="ABC-123",
        ...     name="Cable NYM-J 3x1.5mm²",
        ...     description="Installation cable for indoor use",
        ...     base_uom="M",
        ...     attributes_json={"manufacturer": "ACME", "EAN": "4012345678901", "category": "Cables"},
        ...     uom_conversions_json={"ROLL": 100, "KM": 1000}
        ... )
        'SKU: ABC-123\\nNAME: Cable NYM-J 3x1.5mm²\\nDESC: Installation cable for indoor use\\nATTR: ACME;4012345678901;Cables\\nUOM: base=M; conv={"ROLL":100,"KM":1000}\\n'

    Notes:
        - Missing fields are replaced with empty strings
        - Format is deterministic for same input (stable text_hash)
        - JSON is compact (no spaces) for consistency
    """
    # Extract attributes
    attrs = attributes_json or {}
    manufacturer = attrs.get("manufacturer", "")
    ean = attrs.get("EAN", "")
    category = attrs.get("category", "")

    # Compact JSON for UoM conversions (deterministic formatting)
    uom_conv_compact = json.dumps(uom_conversions_json or {}, separators=(',', ':'), sort_keys=True)

    # Build canonical text per SSOT §7.7.3
    text = (
        f"SKU: {internal_sku}\n"
        f"NAME: {name}\n"
        f"DESC: {description or ''}\n"
        f"ATTR: {manufacturer};{ean};{category}\n"
        f"UOM: base={base_uom or ''}; conv={uom_conv_compact}\n"
    )

    return text


def generate_query_embedding_text(
    customer_sku_raw: Optional[str] = None,
    product_description: Optional[str] = None,
    uom: Optional[str] = None,
) -> str:
    """Generate canonical embedding text for a query (draft line matching).

    SSOT Reference: §7.7.3 - Format:
        CUSTOMER_SKU: {customer_sku_raw}
        DESC: {product_description}
        UOM: {uom}

    Args:
        customer_sku_raw: Customer's SKU from order
        product_description: Product description from order
        uom: Unit of measure from order

    Returns:
        Canonical text string for query embedding

    Example:
        >>> generate_query_embedding_text(
        ...     customer_sku_raw="XYZ-999",
        ...     product_description="Kabel 3x1,5",
        ...     uom="M"
        ... )
        'CUSTOMER_SKU: XYZ-999\\nDESC: Kabel 3x1,5\\nUOM: M\\n'

    Notes:
        - Missing fields are replaced with empty strings
        - Format matches product text structure for better semantic matching
        - Empty SKU/description still produces valid text
    """
    text = (
        f"CUSTOMER_SKU: {customer_sku_raw or ''}\n"
        f"DESC: {product_description or ''}\n"
        f"UOM: {uom or ''}\n"
    )

    return text


def calculate_text_hash(text: str) -> str:
    """Calculate SHA256 hash of text for deduplication.

    Args:
        text: Text to hash (typically from generate_product_embedding_text)

    Returns:
        SHA256 hex digest (64 characters)

    Example:
        >>> calculate_text_hash("SKU: ABC-123\\nNAME: Cable\\n")
        'a3f2b1c0...'  # 64-char hex string

    Notes:
        - Used for deduplication: same text = same hash = skip re-embedding
        - Hash is deterministic for same input
        - Hash stored in product_embedding.text_hash
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def truncate_text_for_embedding(text: str, max_tokens: int = 8191) -> str:
    """Truncate text to fit within token limit.

    OpenAI text-embedding-3-small has 8191 token limit.
    Rough approximation: 1 token ≈ 4 characters.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens (default: 8191 for OpenAI)

    Returns:
        Truncated text

    Notes:
        - This is a rough approximation (4 chars/token)
        - For precise truncation, use tiktoken library
        - Truncation preserves beginning of text (most important info)
    """
    # Rough approximation: 1 token ≈ 4 characters
    max_chars = max_tokens * 4

    if len(text) <= max_chars:
        return text

    # Truncate to max_chars and add ellipsis
    return text[:max_chars - 3] + "..."
