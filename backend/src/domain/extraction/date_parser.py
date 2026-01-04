"""Date parsing utilities for extraction module.

Provides functions to parse dates from various string formats commonly
found in purchase orders, especially German/European formats.

SSOT Reference: §7 (Extraction Logic)
"""

import logging
from datetime import datetime, date
from typing import Optional, List

logger = logging.getLogger(__name__)


# Common date format patterns (order matters - most specific first)
DATE_FORMATS = [
    # ISO format (international standard)
    '%Y-%m-%d',          # 2024-01-15
    '%Y-%m-%dT%H:%M:%S', # 2024-01-15T14:30:00
    '%Y-%m-%d %H:%M:%S', # 2024-01-15 14:30:00

    # European/German formats (DD.MM.YYYY)
    '%d.%m.%Y',          # 15.01.2024
    '%d.%m.%y',          # 15.01.24
    '%d-%m-%Y',          # 15-01-2024
    '%d/%m/%Y',          # 15/01/2024

    # US formats (MM/DD/YYYY)
    '%m/%d/%Y',          # 01/15/2024
    '%m-%d-%Y',          # 01-15-2024

    # Other common formats
    '%d %B %Y',          # 15 January 2024
    '%d %b %Y',          # 15 Jan 2024
    '%B %d, %Y',         # January 15, 2024
    '%b %d, %Y',         # Jan 15, 2024

    # German month names
    '%d. %B %Y',         # 15. Januar 2024
    '%d. %b %Y',         # 15. Jan 2024
]


def parse_date(value: any) -> Optional[date]:
    """Parse date from various string formats.

    Handles common date formats including:
    - ISO format (YYYY-MM-DD)
    - European/German format (DD.MM.YYYY)
    - US format (MM/DD/YYYY)
    - Various date-time formats

    Args:
        value: Date value to parse (str, date, datetime, or None)

    Returns:
        date object or None if parsing fails

    Examples:
        >>> parse_date('2024-01-15')
        date(2024, 1, 15)
        >>> parse_date('15.01.2024')
        date(2024, 1, 15)
        >>> parse_date('01/15/2024')
        date(2024, 1, 15)
        >>> parse_date('invalid')
        None
    """
    if value is None:
        return None

    # Handle date/datetime objects
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()

    # Convert to string and clean up
    if not isinstance(value, str):
        value = str(value)

    value = value.strip()
    if not value:
        return None

    # Try each format
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date()
        except ValueError:
            continue

    # If all formats failed, log warning
    logger.warning(f"Failed to parse date: {value}")
    return None


def parse_date_strict(value: any, formats: Optional[List[str]] = None) -> Optional[date]:
    """Parse date using specific format(s) only.

    Unlike parse_date(), this function only tries the specified formats,
    making it more predictable but less flexible.

    Args:
        value: Date value to parse (str, date, datetime, or None)
        formats: List of strftime format strings to try (defaults to ISO format)

    Returns:
        date object or None if parsing fails

    Examples:
        >>> parse_date_strict('2024-01-15', ['%Y-%m-%d'])
        date(2024, 1, 15)
        >>> parse_date_strict('15.01.2024', ['%d.%m.%Y'])
        date(2024, 1, 15)
        >>> parse_date_strict('15.01.2024', ['%Y-%m-%d'])  # Wrong format
        None
    """
    if value is None:
        return None

    # Handle date/datetime objects
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()

    # Convert to string
    if not isinstance(value, str):
        value = str(value)

    value = value.strip()
    if not value:
        return None

    # Default to ISO format if no formats specified
    if formats is None:
        formats = ['%Y-%m-%d']

    # Try each specified format
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date()
        except ValueError:
            continue

    return None


def format_date_iso(value: any) -> Optional[str]:
    """Format date as ISO string (YYYY-MM-DD).

    Args:
        value: Date value to format (str, date, datetime, or None)

    Returns:
        ISO format string or None if parsing/formatting fails

    Examples:
        >>> format_date_iso(date(2024, 1, 15))
        '2024-01-15'
        >>> format_date_iso('15.01.2024')
        '2024-01-15'
        >>> format_date_iso('invalid')
        None
    """
    parsed = parse_date(value)
    if parsed is None:
        return None

    return parsed.isoformat()


def is_valid_date(value: any) -> bool:
    """Check if value can be parsed as a valid date.

    Args:
        value: Value to check

    Returns:
        True if value can be parsed as date, False otherwise

    Examples:
        >>> is_valid_date('2024-01-15')
        True
        >>> is_valid_date('15.01.2024')
        True
        >>> is_valid_date('invalid')
        False
    """
    return parse_date(value) is not None
