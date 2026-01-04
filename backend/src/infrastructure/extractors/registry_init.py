"""Extractor Registry Initialization - Register all extractors on app startup.

This module provides initialization functions to register all available
extractors with the global registry. Should be called during application
startup (FastAPI lifespan or Celery worker initialization).

SSOT Reference: §7.2 (Extraction Decision Logic)
"""

import logging
from typing import Optional

from excel_extractor import ExcelExtractor
from csv_extractor import CSVExtractor
from pdf_text_extractor import PDFTextExtractor
from extractor_registry import get_global_registry
from domain.documents.ports.object_storage_port import ObjectStoragePort

logger = logging.getLogger(__name__)


def initialize_extractors(storage: ObjectStoragePort) -> None:
    """Initialize and register all extractors with the global registry.

    This function should be called once during application startup to
    populate the global extractor registry with all available implementations.

    Args:
        storage: Object storage adapter (used by extractors to retrieve files)

    Raises:
        ValueError: If storage is None

    Example:
        # In FastAPI lifespan
        from infrastructure.storage import get_storage_adapter
        from infrastructure.extractors.registry_init import initialize_extractors

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            storage = get_storage_adapter()
            initialize_extractors(storage)
            yield

        # In Celery worker
        from celery.signals import worker_init
        from infrastructure.storage import get_storage_adapter
        from infrastructure.extractors.registry_init import initialize_extractors

        @worker_init.connect
        def setup_extractors(**kwargs):
            storage = get_storage_adapter()
            initialize_extractors(storage)
    """
    if storage is None:
        raise ValueError("Storage adapter is required for extractor initialization")

    logger.info("Initializing extractor registry...")

    registry = get_global_registry()

    # Clear registry (in case of re-initialization)
    registry.clear()

    # T036: Register ExcelExtractor for xlsx/xls MIME types
    excel_extractor = ExcelExtractor(storage)
    registry.register(excel_extractor)
    logger.info(
        f"Registered {excel_extractor.version} for MIME types: "
        "application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # T037: Register CSVExtractor for text/csv MIME type
    csv_extractor = CSVExtractor(storage)
    registry.register(csv_extractor)
    logger.info(
        f"Registered {csv_extractor.version} for MIME types: "
        "text/csv, application/csv"
    )

    # T038: Register PDFTextExtractor for application/pdf
    pdf_extractor = PDFTextExtractor(storage)
    registry.register(pdf_extractor)
    logger.info(
        f"Registered {pdf_extractor.version} for MIME type: application/pdf"
    )

    logger.info(
        f"Extractor registry initialized with {len(registry)} extractors. "
        f"Supported MIME types: {registry.list_supported_mime_types()}"
    )


def get_initialized_registry(storage: Optional[ObjectStoragePort] = None):
    """Get global registry, initializing if needed.

    Convenience function that returns the global registry and ensures
    it's initialized with extractors. If registry is empty and storage
    is provided, initializes extractors.

    Args:
        storage: Optional storage adapter (required if registry is empty)

    Returns:
        ExtractorRegistry: Global registry instance

    Raises:
        RuntimeError: If registry is empty and no storage provided

    Warning:
        This is a convenience function. For production code, prefer explicit
        initialization during app startup using initialize_extractors().
    """
    registry = get_global_registry()

    # If registry is empty, try to initialize
    if len(registry) == 0:
        if storage is None:
            raise RuntimeError(
                "Extractor registry is empty and no storage adapter provided. "
                "Call initialize_extractors() during app startup or provide storage parameter."
            )
        initialize_extractors(storage)

    return registry
