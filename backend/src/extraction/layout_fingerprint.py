"""Layout fingerprinting for PDF documents (SSOT §7.10.3)."""

import hashlib
import json
import re
from typing import Any


def calculate_layout_fingerprint(
    page_count: int,
    text: str,
    has_tables: bool | None = None,
) -> str:
    """Calculate layout fingerprint for a PDF document.

    Per SSOT §7.5.4 & §7.10.3: Fingerprint is sha256(structural_metadata_json).

    The fingerprint is used to identify documents with similar structure
    for few-shot learning from feedback corrections.

    Args:
        page_count: Number of pages in PDF
        text: Extracted text from PDF
        has_tables: Whether tables were detected (optional)

    Returns:
        SHA256 hex string of structural metadata
    """
    # Calculate structural metadata
    metadata = {
        "page_count": page_count,
        "avg_line_length": _calculate_avg_line_length(text),
        "has_tables": has_tables if has_tables is not None else _detect_tables(text),
        "text_length_bucket": _bucket_text_length(len(text)),
        "numeric_density": _calculate_numeric_density(text),
    }

    # Sort keys for deterministic hashing
    metadata_json = json.dumps(metadata, sort_keys=True)
    return hashlib.sha256(metadata_json.encode()).hexdigest()


def _calculate_avg_line_length(text: str) -> int:
    """Calculate median line length in characters.

    Args:
        text: PDF text

    Returns:
        Median line length (bucket: 0-50, 50-100, 100-150, 150+)
    """
    lines = text.split("\n")
    if not lines:
        return 0

    line_lengths = [len(line) for line in lines if line.strip()]
    if not line_lengths:
        return 0

    # Calculate median
    sorted_lengths = sorted(line_lengths)
    mid = len(sorted_lengths) // 2
    median = sorted_lengths[mid]

    # Bucket into ranges
    if median < 50:
        return 0
    elif median < 100:
        return 50
    elif median < 150:
        return 100
    else:
        return 150


def _detect_tables(text: str) -> bool:
    """Heuristic: Detect if text likely contains tables.

    Looks for:
    - Multiple pipe characters (|) per line
    - Multiple tab characters
    - Repeated patterns of digits + whitespace

    Args:
        text: PDF text

    Returns:
        True if tables likely present
    """
    lines = text.split("\n")

    # Check for pipe characters (common in text tables)
    pipe_count = sum(1 for line in lines if line.count("|") >= 2)
    if pipe_count > 3:
        return True

    # Check for tabs (common in extracted tables)
    tab_count = sum(1 for line in lines if "\t" in line)
    if tab_count > 5:
        return True

    # Check for repeated number patterns (table rows)
    number_pattern_count = sum(
        1 for line in lines
        if re.search(r'\d+\s+\d+\s+\d+', line)  # At least 3 numbers separated by spaces
    )
    if number_pattern_count > 5:
        return True

    return False


def _bucket_text_length(length: int) -> str:
    """Bucket text length into ranges.

    Args:
        length: Text length in characters

    Returns:
        Bucket string (e.g., '0-1k', '1k-5k', '5k-10k', '10k+')
    """
    if length < 1000:
        return "0-1k"
    elif length < 5000:
        return "1k-5k"
    elif length < 10000:
        return "5k-10k"
    else:
        return "10k+"


def _calculate_numeric_density(text: str) -> str:
    """Calculate density of numeric characters in text.

    Args:
        text: PDF text

    Returns:
        Density bucket ('low', 'medium', 'high')
    """
    if not text:
        return "low"

    # Count digits
    digit_count = sum(1 for c in text if c.isdigit())
    total_chars = len(text)

    if total_chars == 0:
        return "low"

    density = digit_count / total_chars

    if density < 0.1:
        return "low"
    elif density < 0.25:
        return "medium"
    else:
        return "high"


def extract_snippet_for_feedback(text: str, max_length: int = 1500) -> str:
    """Extract first N characters of text as snippet for few-shot examples.

    Per SSOT §7.10.3: Store first 1500 chars as input_snippet.

    Args:
        text: Full PDF text
        max_length: Maximum snippet length

    Returns:
        Text snippet
    """
    return text[:max_length]
