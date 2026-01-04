"""Documents domain module - file storage, document lifecycle, status management

SSOT Reference: §5.4.6 (document table), §5.2.3 (DocumentStatus)
"""

from .document_status import DocumentStatus, can_transition, ALLOWED_TRANSITIONS
from .validation import (
    is_supported_mime_type,
    validate_file_size,
    validate_filename,
    sanitize_filename,
    SUPPORTED_MIME_TYPES,
    MAX_FILE_SIZE,
    MAX_BATCH_FILES,
)

__all__ = [
    "DocumentStatus",
    "can_transition",
    "ALLOWED_TRANSITIONS",
    "is_supported_mime_type",
    "validate_file_size",
    "validate_filename",
    "sanitize_filename",
    "SUPPORTED_MIME_TYPES",
    "MAX_FILE_SIZE",
    "MAX_BATCH_FILES",
]
