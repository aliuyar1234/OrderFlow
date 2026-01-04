"""
Extraction adapters - Helper utilities for extraction.

NOTE: Extractor implementations have been consolidated into infrastructure/extractors/.
This module now contains only helper utilities (column_mapper, format_detector).
"""

from .column_mapper import ColumnMapper
from .format_detector import (
    detect_encoding,
    detect_separator,
    detect_decimal_separator,
    parse_decimal,
    normalize_uom
)

__all__ = [
    'ColumnMapper',
    'detect_encoding',
    'detect_separator',
    'detect_decimal_separator',
    'parse_decimal',
    'normalize_uom',
]
