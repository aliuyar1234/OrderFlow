"""File validation utilities for document uploads

SSOT Reference: §7 (Upload Implementation), spec 007
"""

import os
import re
from typing import Optional, Tuple


# Supported MIME types (SSOT §8.5)
SUPPORTED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'text/csv',
    'application/zip',  # For future ZIP extraction
}

# File size limit (default 100MB, configurable via env)
MAX_FILE_SIZE = int(os.getenv('MAX_UPLOAD_SIZE_BYTES', 100 * 1024 * 1024))

# Batch upload limit
MAX_BATCH_FILES = int(os.getenv('MAX_BATCH_UPLOAD_FILES', 10))


def is_supported_mime_type(mime_type: str) -> bool:
    """Check if MIME type is supported for upload

    Args:
        mime_type: MIME type string (e.g., 'application/pdf')

    Returns:
        True if supported, False otherwise

    Example:
        >>> is_supported_mime_type('application/pdf')
        True
        >>> is_supported_mime_type('application/msword')
        False
    """
    return mime_type in SUPPORTED_MIME_TYPES


def validate_file_size(size_bytes: int, max_size: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """Validate file size is within limits

    Args:
        size_bytes: File size in bytes
        max_size: Maximum allowed size (defaults to MAX_FILE_SIZE)

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_file_size(1024)
        (True, None)
        >>> validate_file_size(0)
        (False, 'File is empty (0 bytes)')
        >>> validate_file_size(200 * 1024 * 1024)
        (False, 'File exceeds maximum size...')
    """
    if max_size is None:
        max_size = MAX_FILE_SIZE

    if size_bytes == 0:
        return False, "File is empty (0 bytes)"

    if size_bytes > max_size:
        return False, f"File exceeds maximum size of {max_size} bytes (got {size_bytes} bytes)"

    return True, None


def validate_filename(filename: str) -> Tuple[bool, Optional[str]]:
    """Validate and sanitize filename

    Args:
        filename: Original filename

    Returns:
        Tuple of (is_valid, error_message)

    Validation rules:
    - Not empty
    - Max 255 characters
    - No path traversal (../, ..\\)
    - No null bytes
    - Contains valid characters

    Example:
        >>> validate_filename('order.pdf')
        (True, None)
        >>> validate_filename('../../etc/passwd')
        (False, 'Filename contains path traversal')
        >>> validate_filename('')
        (False, 'Filename cannot be empty')
    """
    if not filename or len(filename.strip()) == 0:
        return False, "Filename cannot be empty"

    if len(filename) > 255:
        return False, f"Filename exceeds 255 characters (got {len(filename)})"

    # Check for path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return False, "Filename contains path traversal or directory separators"

    # Check for null bytes
    if '\x00' in filename:
        return False, "Filename contains null bytes"

    # Check for control characters
    if any(ord(c) < 32 for c in filename):
        return False, "Filename contains control characters"

    return True, None


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage

    Args:
        filename: Original filename

    Returns:
        Sanitized filename

    Example:
        >>> sanitize_filename('../../order.pdf')
        'order.pdf'
        >>> sanitize_filename('order (copy).pdf')
        'order_copy.pdf'
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Replace problematic characters with underscore
    filename = re.sub(r'[^\w\s.-]', '_', filename)

    # Collapse multiple spaces/underscores
    filename = re.sub(r'[\s_]+', '_', filename)

    # Trim to 255 chars
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        max_name_len = 255 - len(ext)
        filename = name[:max_name_len] + ext

    return filename
