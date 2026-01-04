"""Extractor Registry - Manages available extractors and selects appropriate one.

Registry pattern for managing multiple extractor implementations.
Allows dynamic registration and selection based on MIME type.

SSOT Reference: §7.2 (Extraction Decision Logic)
"""

import logging
from typing import List, Optional

from ...domain.extraction.ports import ExtractorPort

logger = logging.getLogger(__name__)


class ExtractorRegistry:
    """Registry for managing available document extractors.

    Provides centralized management of extractor implementations
    and selection logic based on MIME type and priority.

    Example:
        registry = ExtractorRegistry()
        registry.register(ExcelExtractor(storage))
        registry.register(CSVExtractor(storage))

        extractor = registry.get_extractor('text/csv')
        if extractor:
            result = await extractor.extract(document)
    """

    def __init__(self):
        """Initialize empty registry."""
        self._extractors: List[ExtractorPort] = []

    def register(self, extractor: ExtractorPort) -> None:
        """Register an extractor.

        Args:
            extractor: Extractor implementation to register

        Raises:
            ValueError: If extractor is None
        """
        if extractor is None:
            raise ValueError("Cannot register None as extractor")

        self._extractors.append(extractor)
        logger.info(f"Registered extractor: {extractor.version}")

    def get_extractor(self, mime_type: str) -> Optional[ExtractorPort]:
        """Get appropriate extractor for MIME type.

        Selects extractor based on:
        1. MIME type support (calls extractor.supports())
        2. Priority (lower number = higher priority)

        Args:
            mime_type: MIME type of document (e.g., 'text/csv')

        Returns:
            ExtractorPort instance or None if no extractor supports this MIME type

        Example:
            >>> registry = ExtractorRegistry()
            >>> registry.register(ExcelExtractor(storage))
            >>> extractor = registry.get_extractor('application/vnd.ms-excel')
            >>> print(extractor.version)
            'excel_v1'
        """
        if not mime_type:
            logger.warning("get_extractor called with empty mime_type")
            return None

        # Find all extractors that support this MIME type
        compatible_extractors = [
            extractor
            for extractor in self._extractors
            if extractor.supports(mime_type)
        ]

        if not compatible_extractors:
            logger.warning(f"No extractor found for MIME type: {mime_type}")
            return None

        # Sort by priority (lower = higher priority)
        compatible_extractors.sort(key=lambda e: e.priority)

        # Return highest priority extractor
        selected = compatible_extractors[0]
        logger.debug(
            f"Selected extractor {selected.version} for MIME type {mime_type} "
            f"(priority={selected.priority})"
        )

        return selected

    def list_extractors(self) -> List[ExtractorPort]:
        """Get list of all registered extractors.

        Returns:
            List of registered extractors
        """
        return list(self._extractors)

    def list_supported_mime_types(self) -> List[str]:
        """Get list of all supported MIME types.

        Returns:
            List of unique MIME types supported by registered extractors

        Note:
            This is a convenience method that tests common MIME types.
            It may not be exhaustive.
        """
        common_mime_types = [
            'application/pdf',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/csv',
            'application/csv',
        ]

        supported = set()
        for mime_type in common_mime_types:
            if self.get_extractor(mime_type) is not None:
                supported.add(mime_type)

        return sorted(supported)

    def clear(self) -> None:
        """Clear all registered extractors.

        Useful for testing or re-initialization.
        """
        count = len(self._extractors)
        self._extractors.clear()
        logger.info(f"Cleared {count} extractors from registry")

    def __len__(self) -> int:
        """Get number of registered extractors.

        Returns:
            Number of extractors in registry
        """
        return len(self._extractors)


# Global registry instance (singleton pattern)
_global_registry: Optional[ExtractorRegistry] = None


def get_global_registry() -> ExtractorRegistry:
    """Get global extractor registry singleton.

    Lazy-initialized singleton for application-wide extractor registry.
    The registry is initialized empty - extractors must be registered
    during application startup.

    Returns:
        Global ExtractorRegistry instance

    Example:
        # During app startup
        from infrastructure.extractors import get_global_registry
        from infrastructure.extractors import ExcelExtractor, CSVExtractor
        from infrastructure.storage import get_storage_adapter

        registry = get_global_registry()
        storage = get_storage_adapter()

        registry.register(ExcelExtractor(storage))
        registry.register(CSVExtractor(storage))

        # Later in workers
        registry = get_global_registry()
        extractor = registry.get_extractor(document.mime_type)
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = ExtractorRegistry()
        logger.debug("Initialized global extractor registry")

    return _global_registry


def reset_global_registry() -> None:
    """Reset global registry (primarily for testing).

    Clears the global registry singleton, forcing re-initialization
    on next access.

    Warning:
        This should only be used in tests. Do not call in production code.
    """
    global _global_registry
    _global_registry = None
    logger.debug("Reset global extractor registry")
