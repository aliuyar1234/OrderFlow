"""AI domain models and enums"""

from enum import Enum


class AICallType(str, Enum):
    """
    AI call types for tracking and logging.

    SSOT Reference: §5.2.10 (AICallType enum)
    """
    LLM_EXTRACT_PDF_TEXT = "LLM_EXTRACT_PDF_TEXT"
    LLM_EXTRACT_PDF_VISION = "LLM_EXTRACT_PDF_VISION"
    LLM_EXTRACT_EXCEL = "LLM_EXTRACT_EXCEL"
    LLM_REPAIR_JSON = "LLM_REPAIR_JSON"
    LLM_CUSTOMER_HINT = "LLM_CUSTOMER_HINT"
    EMBEDDING_PRODUCT = "EMBEDDING_PRODUCT"
    EMBEDDING_DOCUMENT = "EMBEDDING_DOCUMENT"
