"""
Format detection utilities for CSV/Excel extraction.
Implements auto-detection of separators, decimal formats, and encoding per SSOT §7.2.
"""
import re
from typing import Tuple, Optional, List
import chardet


def detect_encoding(raw_bytes: bytes) -> str:
    """
    Detect character encoding of file.
    Per SSOT FR-014: Fallback order UTF-8 → ISO-8859-1 → Windows-1252.

    Args:
        raw_bytes: File contents as bytes

    Returns:
        Detected encoding name (e.g., 'utf-8', 'iso-8859-1')
    """
    # Try chardet first
    result = chardet.detect(raw_bytes)
    detected = result.get('encoding')

    if detected and result.get('confidence', 0) > 0.7:
        return detected.lower()

    # Fallback order per SSOT
    for encoding in ['utf-8', 'iso-8859-1', 'windows-1252']:
        try:
            raw_bytes.decode(encoding)
            return encoding
        except (UnicodeDecodeError, AttributeError):
            continue

    # Last resort
    return 'utf-8'


def detect_separator(sample_lines: List[str]) -> str:
    """
    Auto-detect CSV separator from sample lines.
    Per SSOT FR-001: Support `;`, `,`, `\t`, `|`.

    Args:
        sample_lines: First N lines of file (recommend 5-10 lines)

    Returns:
        Most likely separator character
    """
    candidates = {';': 0, ',': 0, '\t': 0, '|': 0}

    for line in sample_lines:
        if not line.strip():
            continue

        # Count occurrences of each separator
        for sep in candidates.keys():
            count = line.count(sep)
            if count > 0:
                candidates[sep] += count

    # Return separator with highest count
    if any(candidates.values()):
        return max(candidates, key=candidates.get)

    # Default to comma if ambiguous
    return ','


def detect_decimal_separator(sample_lines: List[str], field_separator: str) -> str:
    """
    Detect if comma or dot is used as decimal separator.
    Per SSOT FR-002: Support comma (,) as decimal separator (DACH requirement).

    Args:
        sample_lines: First N lines of file
        field_separator: Already-detected field separator

    Returns:
        ',' for comma decimal, '.' for dot decimal
    """
    # Pattern to match numbers with comma or dot
    # Examples: "10,50", "1.234,56", "10.50", "1,234.56"
    comma_pattern = re.compile(r'\d+,\d{1,2}(?!\d)')  # Number with comma followed by 1-2 digits
    dot_pattern = re.compile(r'\d+\.\d{1,2}(?!\d)')   # Number with dot followed by 1-2 digits

    comma_count = 0
    dot_count = 0

    for line in sample_lines:
        if not line.strip():
            continue

        # Split by field separator to analyze numeric fields
        fields = line.split(field_separator)

        for field in fields:
            field = field.strip().strip('"').strip("'")

            # Count decimal separator patterns
            if comma_pattern.search(field):
                # Check if it's likely a decimal (not thousands separator)
                # In DACH format, comma is decimal: 10,50
                # In US format with thousands: 1,234.56 (comma has 3+ digits after)
                if re.search(r'\d+,\d{1,2}$', field):
                    comma_count += 1

            if dot_pattern.search(field):
                # Check if it's likely a decimal (not thousands separator)
                if re.search(r'\d+\.\d{1,2}$', field):
                    dot_count += 1

    # If field separator is comma, decimal must be dot
    if field_separator == ',':
        return '.'

    # If we found more comma decimals, use comma
    if comma_count > dot_count:
        return ','

    # Default to dot (international standard)
    return '.'


def parse_decimal(value: str, decimal_separator: str = '.') -> Optional[float]:
    """
    Parse a decimal number with configurable decimal separator.
    Per SSOT FR-002: Handle comma as decimal separator.

    Args:
        value: String value to parse (e.g., "10,50", "1.234,56", "10.50")
        decimal_separator: ',' or '.'

    Returns:
        Parsed float value or None if invalid

    Examples:
        >>> parse_decimal("10,50", ",")
        10.5
        >>> parse_decimal("1.234,56", ",")
        1234.56
        >>> parse_decimal("10.50", ".")
        10.5
    """
    if not value or not isinstance(value, str):
        return None

    # Remove whitespace
    value = value.strip().strip('"').strip("'")

    if not value:
        return None

    try:
        if decimal_separator == ',':
            # DACH format: 1.234,56 → remove dots (thousands), replace comma with dot
            value = value.replace('.', '').replace(',', '.')
        else:
            # US/International format: 1,234.56 → remove commas (thousands)
            value = value.replace(',', '')

        return float(value)
    except (ValueError, AttributeError):
        return None


def normalize_uom(raw_uom: Optional[str]) -> Optional[str]:
    """
    Normalize UoM to canonical codes per SSOT §6.2.

    Args:
        raw_uom: Raw UoM string from document

    Returns:
        Canonical UoM code or None if unknown
    """
    if not raw_uom:
        return None

    # Normalize to uppercase and strip
    raw_uom = raw_uom.strip().upper()

    # UoM mapping per SSOT §6.2
    uom_mapping = {
        # Piece/Units
        'STK': 'ST', 'STÜCK': 'ST', 'STUECK': 'ST', 'PCS': 'ST', 'PIECE': 'ST',
        'EA': 'ST', 'EACH': 'ST', 'PC': 'ST',

        # Length
        'METER': 'M', 'MTR': 'M',
        'ZENTIMETER': 'CM', 'CENTIMETER': 'CM',
        'MILLIMETER': 'MM',

        # Weight
        'KILOGRAMM': 'KG', 'KILO': 'KG',
        'GRAMM': 'G',

        # Volume
        'LITER': 'L',
        'MILLILITER': 'ML',

        # Packaging
        'KARTON': 'KAR', 'CTN': 'KAR', 'CARTON': 'KAR',
        'PALETTE': 'PAL', 'PALLET': 'PAL',

        # Set
        'SATZ': 'SET',
    }

    # Check if already canonical
    canonical_codes = ['ST', 'M', 'CM', 'MM', 'KG', 'G', 'L', 'ML', 'KAR', 'PAL', 'SET']
    if raw_uom in canonical_codes:
        return raw_uom

    # Map from common variants
    return uom_mapping.get(raw_uom)
