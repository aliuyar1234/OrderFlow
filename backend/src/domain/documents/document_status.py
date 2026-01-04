"""DocumentStatus state machine for document processing lifecycle

SSOT Reference: §5.2.3 (DocumentStatus enum and state transitions)
"""

from enum import Enum
from typing import Optional, Dict, List


class DocumentStatus(str, Enum):
    """Document processing status enum

    State flow:
    UPLOADED → STORED → PROCESSING → EXTRACTED or FAILED
    FAILED can retry to PROCESSING
    """
    UPLOADED = "UPLOADED"      # File received via upload
    STORED = "STORED"          # File persisted to object storage
    PROCESSING = "PROCESSING"  # Extraction in progress
    EXTRACTED = "EXTRACTED"    # Extraction complete (terminal success)
    FAILED = "FAILED"          # Processing failed (can retry)


# State transition rules
ALLOWED_TRANSITIONS: Dict[Optional[DocumentStatus], List[DocumentStatus]] = {
    None: [DocumentStatus.UPLOADED],
    DocumentStatus.UPLOADED: [DocumentStatus.STORED, DocumentStatus.FAILED],
    DocumentStatus.STORED: [DocumentStatus.PROCESSING, DocumentStatus.FAILED],
    DocumentStatus.PROCESSING: [DocumentStatus.EXTRACTED, DocumentStatus.FAILED],
    DocumentStatus.EXTRACTED: [],  # Terminal success state
    DocumentStatus.FAILED: [DocumentStatus.PROCESSING]  # Allow retry
}


def can_transition(from_status: Optional[DocumentStatus], to_status: DocumentStatus) -> bool:
    """Validate if status transition is allowed

    Args:
        from_status: Current status (None for new documents)
        to_status: Target status

    Returns:
        True if transition is allowed, False otherwise

    Example:
        >>> can_transition(DocumentStatus.UPLOADED, DocumentStatus.STORED)
        True
        >>> can_transition(DocumentStatus.EXTRACTED, DocumentStatus.PROCESSING)
        False
    """
    allowed = ALLOWED_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def get_allowed_transitions(from_status: Optional[DocumentStatus]) -> List[DocumentStatus]:
    """Get list of allowed transitions from current status

    Args:
        from_status: Current status (None for new documents)

    Returns:
        List of allowed target statuses

    Example:
        >>> get_allowed_transitions(DocumentStatus.UPLOADED)
        [DocumentStatus.STORED, DocumentStatus.FAILED]
    """
    return ALLOWED_TRANSITIONS.get(from_status, [])
