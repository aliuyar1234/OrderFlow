"""
Extraction ports (interfaces) following Hexagonal Architecture.
Per SSOT §3.5, extractors are pluggable adapters.
"""
from abc import ABC, abstractmethod
from typing import BinaryIO
from .models import ExtractionResult


class ExtractorPort(ABC):
    """
    Port interface for document extractors.
    All extractors (CSV, Excel, PDF, LLM) must implement this interface.
    """

    @abstractmethod
    def extract(self, file_content: BinaryIO, filename: str, org_id: str) -> ExtractionResult:
        """
        Extract structured order data from a document.

        Args:
            file_content: Binary file content
            filename: Original filename (used for content type detection)
            org_id: Organization ID (for org-specific settings)

        Returns:
            ExtractionResult with canonical output and metrics

        Raises:
            ValueError: If file format is invalid or unsupported
            Exception: For other extraction errors
        """
        pass

    @abstractmethod
    def can_handle(self, content_type: str, filename: str) -> bool:
        """
        Check if this extractor can handle the given file type.

        Args:
            content_type: MIME type (e.g., 'text/csv', 'application/pdf')
            filename: Original filename

        Returns:
            True if this extractor can process the file
        """
        pass
