"""Domain layer for extraction module.

This module defines the extraction domain logic, including canonical output schemas,
confidence calculation, and port interfaces for extractors.

SSOT References: §7 (Extraction Logic)
"""

from .canonical_output import (
    ExtractionLineItem,
    ExtractionOrderHeader,
    CanonicalExtractionOutput,
)
from .confidence import calculate_confidence

__all__ = [
    "ExtractionLineItem",
    "ExtractionOrderHeader",
    "CanonicalExtractionOutput",
    "calculate_confidence",
]
