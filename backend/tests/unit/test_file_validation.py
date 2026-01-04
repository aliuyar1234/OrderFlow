"""Unit tests for file validation utilities

SSOT Reference: §8.5 (Upload Implementation)
Spec: 007-document-upload
"""

import pytest
from backend.src.domain.documents import (
    is_supported_mime_type,
    validate_file_size,
    validate_filename,
    sanitize_filename,
    SUPPORTED_MIME_TYPES,
    MAX_FILE_SIZE,
)


class TestMimeTypeValidation:
    """Test MIME type validation for uploads"""

    def test_supported_mime_types_constant(self):
        """Test SUPPORTED_MIME_TYPES contains expected types"""
        assert 'application/pdf' in SUPPORTED_MIME_TYPES
        assert 'application/vnd.ms-excel' in SUPPORTED_MIME_TYPES
        assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in SUPPORTED_MIME_TYPES
        assert 'text/csv' in SUPPORTED_MIME_TYPES

    def test_pdf_mime_type_supported(self):
        """Test PDF MIME type is supported"""
        assert is_supported_mime_type('application/pdf') is True

    def test_excel_xls_mime_type_supported(self):
        """Test Excel .xls MIME type is supported"""
        assert is_supported_mime_type('application/vnd.ms-excel') is True

    def test_excel_xlsx_mime_type_supported(self):
        """Test Excel .xlsx MIME type is supported"""
        assert is_supported_mime_type('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') is True

    def test_csv_mime_type_supported(self):
        """Test CSV MIME type is supported"""
        assert is_supported_mime_type('text/csv') is True

    def test_zip_mime_type_supported(self):
        """Test ZIP MIME type is supported (for future use)"""
        assert is_supported_mime_type('application/zip') is True

    def test_unsupported_mime_type_docx(self):
        """Test Word documents (.docx) are not supported"""
        assert is_supported_mime_type('application/vnd.openxmlformats-officedocument.wordprocessingml.document') is False

    def test_unsupported_mime_type_image(self):
        """Test image types are not supported"""
        assert is_supported_mime_type('image/jpeg') is False
        assert is_supported_mime_type('image/png') is False

    def test_unsupported_mime_type_executable(self):
        """Test executable types are not supported"""
        assert is_supported_mime_type('application/x-executable') is False
        assert is_supported_mime_type('application/x-msdownload') is False

    def test_unsupported_mime_type_text(self):
        """Test plain text is not supported"""
        assert is_supported_mime_type('text/plain') is False


class TestFileSizeValidation:
    """Test file size validation"""

    def test_valid_small_file(self):
        """Test valid small file (1KB)"""
        is_valid, error = validate_file_size(1024)
        assert is_valid is True
        assert error is None

    def test_valid_medium_file(self):
        """Test valid medium file (10MB)"""
        is_valid, error = validate_file_size(10 * 1024 * 1024)
        assert is_valid is True
        assert error is None

    def test_valid_large_file_at_limit(self):
        """Test file exactly at size limit (100MB default)"""
        is_valid, error = validate_file_size(MAX_FILE_SIZE)
        assert is_valid is True
        assert error is None

    def test_empty_file(self):
        """Test empty file (0 bytes) is rejected"""
        is_valid, error = validate_file_size(0)
        assert is_valid is False
        assert "empty" in error.lower()

    def test_file_exceeds_limit(self):
        """Test file exceeding size limit is rejected"""
        is_valid, error = validate_file_size(MAX_FILE_SIZE + 1)
        assert is_valid is False
        assert "exceeds maximum size" in error.lower()

    def test_very_large_file(self):
        """Test very large file (500MB) is rejected"""
        is_valid, error = validate_file_size(500 * 1024 * 1024)
        assert is_valid is False
        assert "exceeds maximum size" in error.lower()

    def test_custom_max_size(self):
        """Test custom max size parameter"""
        custom_max = 5 * 1024 * 1024  # 5MB
        is_valid, error = validate_file_size(6 * 1024 * 1024, max_size=custom_max)
        assert is_valid is False
        assert "exceeds maximum size" in error.lower()


class TestFilenameValidation:
    """Test filename validation"""

    def test_valid_simple_filename(self):
        """Test valid simple filename"""
        is_valid, error = validate_filename('order.pdf')
        assert is_valid is True
        assert error is None

    def test_valid_filename_with_spaces(self):
        """Test valid filename with spaces"""
        is_valid, error = validate_filename('my order.pdf')
        assert is_valid is True
        assert error is None

    def test_valid_filename_with_numbers(self):
        """Test valid filename with numbers"""
        is_valid, error = validate_filename('order_12345.xlsx')
        assert is_valid is True
        assert error is None

    def test_empty_filename(self):
        """Test empty filename is rejected"""
        is_valid, error = validate_filename('')
        assert is_valid is False
        assert "empty" in error.lower()

    def test_whitespace_only_filename(self):
        """Test whitespace-only filename is rejected"""
        is_valid, error = validate_filename('   ')
        assert is_valid is False
        assert "empty" in error.lower()

    def test_filename_too_long(self):
        """Test filename exceeding 255 characters is rejected"""
        long_name = 'a' * 256 + '.pdf'
        is_valid, error = validate_filename(long_name)
        assert is_valid is False
        assert "exceeds 255 characters" in error.lower()

    def test_filename_with_path_traversal_unix(self):
        """Test filename with Unix path traversal is rejected"""
        is_valid, error = validate_filename('../../etc/passwd')
        assert is_valid is False
        assert "path traversal" in error.lower()

    def test_filename_with_path_traversal_windows(self):
        """Test filename with Windows path traversal is rejected"""
        is_valid, error = validate_filename('..\\..\\windows\\system32\\config')
        assert is_valid is False
        assert "path traversal" in error.lower()

    def test_filename_with_forward_slash(self):
        """Test filename with forward slash is rejected"""
        is_valid, error = validate_filename('folder/file.pdf')
        assert is_valid is False
        assert "path traversal" in error.lower()

    def test_filename_with_backslash(self):
        """Test filename with backslash is rejected"""
        is_valid, error = validate_filename('folder\\file.pdf')
        assert is_valid is False
        assert "path traversal" in error.lower()

    def test_filename_with_null_byte(self):
        """Test filename with null byte is rejected"""
        is_valid, error = validate_filename('file\x00.pdf')
        assert is_valid is False
        assert "null byte" in error.lower()

    def test_filename_with_control_characters(self):
        """Test filename with control characters is rejected"""
        is_valid, error = validate_filename('file\x01.pdf')
        assert is_valid is False
        assert "control character" in error.lower()


class TestFilenameSanitization:
    """Test filename sanitization"""

    def test_sanitize_simple_filename(self):
        """Test sanitizing simple filename (no changes)"""
        assert sanitize_filename('order.pdf') == 'order.pdf'

    def test_sanitize_path_traversal(self):
        """Test sanitizing path traversal removes directory components"""
        assert sanitize_filename('../../order.pdf') == 'order.pdf'

    def test_sanitize_special_characters(self):
        """Test sanitizing special characters replaces with underscore"""
        assert sanitize_filename('order (copy).pdf') == 'order_copy.pdf'

    def test_sanitize_multiple_spaces(self):
        """Test sanitizing multiple spaces collapses to single underscore"""
        result = sanitize_filename('order   copy.pdf')
        assert '__' not in result  # No double underscores

    def test_sanitize_long_filename(self):
        """Test sanitizing filename exceeding 255 chars truncates while preserving extension"""
        long_name = 'a' * 300 + '.pdf'
        result = sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith('.pdf')

    def test_sanitize_windows_path(self):
        """Test sanitizing Windows path removes directory components"""
        assert sanitize_filename('C:\\Users\\test\\order.pdf') == 'order.pdf'

    def test_sanitize_unix_path(self):
        """Test sanitizing Unix path removes directory components"""
        assert sanitize_filename('/home/user/order.pdf') == 'order.pdf'
