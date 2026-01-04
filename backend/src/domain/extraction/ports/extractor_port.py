"""ExtractorPort interface for document extraction.

Defines the contract that all extractors (Excel, CSV, PDF, LLM) must implement.
This port enables swapping extraction strategies without changing domain logic.

SSOT Reference: §7.2 (Extraction Decision Logic)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any

from ..canonical_output import CanonicalExtractionOutput


@dataclass
class ExtractionResult:
    """Result of an extraction operation.

    Attributes:
        success: True if extraction completed without errors
        output: Canonical extraction output (None if failed)
        error: Error message if extraction failed (None if success)
        confidence: Confidence score 0.0-1.0 (0.0 if failed)
        metrics: Dict of metrics (runtime_ms, page_count, etc.)
        extractor_version: Version identifier of extractor used
    """

    success: bool
    output: Optional[CanonicalExtractionOutput] = None
    error: Optional[str] = None
    confidence: float = 0.0
    metrics: dict = None
    extractor_version: str = ""

    def __post_init__(self):
        """Initialize metrics dict if None"""
        if self.metrics is None:
            self.metrics = {}


class ExtractorPort(ABC):
    """Port interface for document extractors.

    All extractors must implement this interface. The extraction pipeline
    uses this interface without knowing about specific extractor implementations.

    Example implementations:
    - ExcelExtractor: Rule-based extraction from Excel files
    - CSVExtractor: Rule-based extraction from CSV files
    - PDFTextExtractor: Rule-based extraction from text-based PDFs
    - LLMExtractor: LLM-based extraction for complex/scanned documents
    """

    @abstractmethod
    async def extract(self, document: Any) -> ExtractionResult:
        """Extract structured order data from document.

        Args:
            document: Document entity with:
                - id: UUID
                - org_id: UUID
                - storage_key: S3 key to retrieve file
                - mime_type: MIME type of file
                - file_size: Size in bytes
                - filename: Original filename

        Returns:
            ExtractionResult with canonical output or error

        Raises:
            Should not raise - all errors should be caught and returned
            in ExtractionResult.error field for proper tracking.
        """
        pass

    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type.

        Args:
            mime_type: MIME type string (e.g., 'application/pdf')

        Returns:
            True if this extractor can handle this MIME type

        Example:
            >>> extractor = ExcelExtractor()
            >>> extractor.supports('application/vnd.ms-excel')
            True
            >>> extractor.supports('application/pdf')
            False
        """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Extractor version identifier for tracking.

        Format: <type>_v<number> (e.g., 'excel_v1', 'pdf_rule_v2', 'llm_gpt4_v1')

        This is stored in extraction_run.extractor_version to track which
        version extracted each document. Useful for debugging, A/B testing,
        and rollback if a version has issues.

        Returns:
            Version string
        """
        pass

    @property
    def priority(self) -> int:
        """Priority for extractor selection (lower = higher priority).

        When multiple extractors support the same MIME type, the one with
        lower priority number is selected first. Default is 100.

        Examples:
            - Rule-based extractors: 10 (try first, fast and cheap)
            - LLM extractors: 90 (fallback, slower and costly)

        Returns:
            Priority integer (default 100)
        """
        return 100
