"""Extractor implementations - Concrete adapters for extraction ports.

Contains rule-based extractors for Excel, CSV, and PDF files.
"""

from .excel_extractor import ExcelExtractor
from .csv_extractor import CSVExtractor
from .extractor_registry import ExtractorRegistry, get_global_registry

__all__ = [
    "ExcelExtractor",
    "CSVExtractor",
    "ExtractorRegistry",
    "get_global_registry",
]
