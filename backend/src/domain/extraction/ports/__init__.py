"""Port interfaces for extraction domain.

Defines abstract interfaces that infrastructure adapters must implement.
This maintains hexagonal architecture - domain doesn't depend on infrastructure.
"""

from .extractor_port import ExtractorPort, ExtractionResult

__all__ = ["ExtractorPort", "ExtractionResult"]
