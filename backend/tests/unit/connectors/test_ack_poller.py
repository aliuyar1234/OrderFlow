"""Unit tests for Ack Poller.

Tests acknowledgment file processing and export status updates.

SSOT Reference: T-606 (Ack poller), §12.2 (Ack mechanism)
"""

import json
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

from workers.connectors.ack_poller import (
    extract_draft_order_id,
    process_ack_data,
    poll_acks_filesystem
)
from models import ERPConnection, ERPExport, ERPExportStatus


class TestAckFilenameExtraction:
    """Test draft_order_id extraction from ack filenames."""

    def test_extract_draft_order_id_from_ack_file(self):
        """Test extraction from ack_ prefix file."""
        filename = "ack_sales_order_abc12345_20251227_100000_def67890.json"
        draft_id = extract_draft_order_id(filename)
        assert draft_id == "abc12345"

    def test_extract_draft_order_id_from_error_file(self):
        """Test extraction from error_ prefix file."""
        filename = "error_sales_order_xyz98765_20251227_153000_uvw12345.json"
        draft_id = extract_draft_order_id(filename)
        assert draft_id == "xyz98765"

    def test_extract_draft_order_id_with_full_uuid(self):
        """Test extraction with full UUID format."""
        filename = "ack_sales_order_550e8400-e29b-41d4-a716-446655440000_20251227_100000_abc12345.json"
        draft_id = extract_draft_order_id(filename)
        assert draft_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_extract_draft_order_id_invalid_pattern(self):
        """Test extraction fails for invalid pattern."""
        filename = "invalid_file.json"
        draft_id = extract_draft_order_id(filename)
        assert draft_id is None

    def test_extract_draft_order_id_missing_prefix(self):
        """Test extraction fails without ack/error prefix."""
        filename = "sales_order_abc12345_20251227_100000_def67890.json"
        draft_id = extract_draft_order_id(filename)
        assert draft_id is None


class TestAckDataProcessing:
    """Test ack data processing logic."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        from unittest.mock import Mock
        return Mock()

    @pytest.fixture
    def sample_connector(self):
        """Create sample ERP connection."""
        connector = ERPConnection()
        connector.id = uuid4()
        connector.org_id = uuid4()
        connector.connector_type = "DROPZONE_JSON_V1"
        connector.active = True
        return connector

    @pytest.fixture
    def sample_export(self, sample_connector):
        """Create sample ERP export."""
        export = ERPExport()
        export.id = uuid4()
        export.org_id = sample_connector.org_id
        export.erp_connection_id = sample_connector.id
        export.draft_order_id = uuid4()
        export.status = ERPExportStatus.SENT.value
        export.created_at = datetime.now(timezone.utc)
        return export

    def test_process_ack_data_success(self, db_session, sample_connector, sample_export):
        """Test processing successful ack file updates status to ACKED."""
        from unittest.mock import Mock

        # Setup mock query
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.first.return_value = sample_export
        db_session.query.return_value = query_mock

        ack_filename = f"ack_sales_order_{sample_export.draft_order_id}_20251227_100000_abc12345.json"
        ack_data = {
            'status': 'ACKED',
            'erp_order_id': 'SO-2025-000123',
            'processed_at': '2025-12-26T10:01:00Z'
        }

        process_ack_data(db_session, sample_connector, ack_filename, ack_data)

        # Verify status updated
        assert sample_export.status == ERPExportStatus.ACKED.value
        assert sample_export.erp_order_id == 'SO-2025-000123'
        assert db_session.commit.called

    def test_process_ack_data_failure(self, db_session, sample_connector, sample_export):
        """Test processing error ack file updates status to FAILED."""
        from unittest.mock import Mock

        # Setup mock query
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.first.return_value = sample_export
        db_session.query.return_value = query_mock

        ack_filename = f"error_sales_order_{sample_export.draft_order_id}_20251227_100000_abc12345.json"
        ack_data = {
            'status': 'FAILED',
            'error_code': 'ERP_VALIDATION',
            'message': 'Unknown customer 4711',
            'processed_at': '2025-12-26T10:01:00Z'
        }

        process_ack_data(db_session, sample_connector, ack_filename, ack_data)

        # Verify status updated
        assert sample_export.status == ERPExportStatus.FAILED.value
        assert sample_export.error_json is not None
        assert sample_export.error_json['error_code'] == 'ERP_VALIDATION'
        assert sample_export.error_json['message'] == 'Unknown customer 4711'
        assert db_session.commit.called


class TestFilesystemAckPolling:
    """Test filesystem ack polling."""

    @pytest.fixture
    def sample_connector(self):
        """Create sample ERP connection."""
        connector = ERPConnection()
        connector.id = uuid4()
        connector.org_id = uuid4()
        connector.connector_type = "DROPZONE_JSON_V1"
        connector.active = True
        return connector

    @pytest.fixture
    def sample_export(self, sample_connector):
        """Create sample ERP export."""
        export = ERPExport()
        export.id = uuid4()
        export.org_id = sample_connector.org_id
        export.erp_connection_id = sample_connector.id
        export.draft_order_id = uuid4()
        export.status = ERPExportStatus.SENT.value
        export.created_at = datetime.now(timezone.utc)
        return export

    def test_poll_acks_filesystem_processes_ack_file(self, tmp_path, sample_connector, sample_export):
        """Test that ack file is processed and moved to processed/ directory."""
        from unittest.mock import Mock

        # Setup ack directory
        ack_path = tmp_path / "acks"
        ack_path.mkdir()

        # Create ack file
        ack_filename = f"ack_sales_order_{sample_export.draft_order_id}_20251227_100000_abc12345.json"
        ack_file = ack_path / ack_filename
        ack_data = {
            'status': 'ACKED',
            'erp_order_id': 'SO-123',
            'processed_at': '2025-12-26T10:01:00Z'
        }
        ack_file.write_text(json.dumps(ack_data))

        # Setup mock DB
        db_session = Mock()
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.first.return_value = sample_export
        db_session.query.return_value = query_mock

        config = {
            'mode': 'filesystem',
            'ack_path': str(ack_path)
        }

        # Poll acks
        acks_processed = poll_acks_filesystem(db_session, sample_connector, config)

        # Verify
        assert acks_processed == 1
        assert not ack_file.exists()  # Original file moved

        # Check processed directory
        processed_dir = ack_path / 'processed'
        assert processed_dir.exists()
        processed_file = processed_dir / ack_filename
        assert processed_file.exists()

    def test_poll_acks_filesystem_handles_malformed_json(self, tmp_path, sample_connector):
        """Test that malformed JSON is moved to error/ directory."""
        from unittest.mock import Mock

        # Setup ack directory
        ack_path = tmp_path / "acks"
        ack_path.mkdir()

        # Create malformed ack file
        ack_filename = "ack_sales_order_abc12345_20251227_100000_def67890.json"
        ack_file = ack_path / ack_filename
        ack_file.write_text("{ invalid json")

        db_session = Mock()

        config = {
            'mode': 'filesystem',
            'ack_path': str(ack_path)
        }

        # Poll acks (should not crash)
        acks_processed = poll_acks_filesystem(db_session, sample_connector, config)

        # Verify malformed file moved to error/
        assert acks_processed == 0
        assert not ack_file.exists()

        error_dir = ack_path / 'error'
        assert error_dir.exists()
        error_file = error_dir / ack_filename
        assert error_file.exists()
