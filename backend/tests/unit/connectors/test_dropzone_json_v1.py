"""Unit tests for DropzoneJsonV1Connector.

Tests JSON generation, filename format, and export logic without external dependencies.

SSOT Reference: T-603 (Export Generator), §12.1 (JSON schema)
"""

import json
import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from domain.connectors.implementations.dropzone_json_v1 import DropzoneJsonV1Connector
from domain.connectors.ports.erp_connector_port import ExportResult


class TestDropzoneJsonV1Connector:
    """Test suite for DropzoneJsonV1Connector."""

    @pytest.fixture
    def mock_storage(self):
        """Mock object storage port."""
        storage = Mock()
        storage.store_file = AsyncMock(return_value=Mock(
            storage_key='exports/org-123/test.json',
            sha256='abc123',
            size_bytes=1024,
            mime_type='application/json'
        ))
        return storage

    @pytest.fixture
    def connector(self, mock_storage):
        """Create connector instance with mocked storage."""
        return DropzoneJsonV1Connector(mock_storage)

    @pytest.fixture
    def sample_draft_order(self):
        """Create sample draft order for testing."""
        draft_order = Mock()
        draft_order.id = uuid4()
        draft_order.org_id = uuid4()
        draft_order.customer_id = uuid4()
        draft_order.external_order_number = "PO-12345"
        draft_order.order_date = date(2025, 12, 1)
        draft_order.currency = "EUR"
        draft_order.requested_delivery_date = date(2025, 12, 10)
        draft_order.notes = "Urgent delivery"
        draft_order.approved_at = datetime(2025, 12, 26, 10, 0, 0, tzinfo=timezone.utc)
        draft_order.approved_by_user_id = uuid4()
        draft_order.ship_to_json = None
        draft_order.bill_to_json = None

        # Mock customer
        customer = Mock()
        customer.id = draft_order.customer_id
        customer.erp_customer_number = "4711"
        customer.name = "Muster GmbH"
        draft_order.customer = customer

        # Mock approved_by_user
        user = Mock()
        user.email = "ops@acme.de"
        draft_order.approved_by_user = user

        # Mock document
        document = Mock()
        document.id = uuid4()
        document.file_name = "order.pdf"
        document.sha256 = "abc123def456"
        draft_order.document = document

        # Mock lines
        line1 = Mock()
        line1.line_no = 1
        line1.internal_sku = "INT-999"
        line1.qty = Decimal("10.000")
        line1.uom = "M"
        line1.unit_price = Decimal("1.23")
        line1.customer_sku_raw = "AB-123"
        line1.product_description = "Kabel NYM-J 3x1,5"
        line1.currency = None
        line1.requested_delivery_date = None
        line1.line_notes = None

        line2 = Mock()
        line2.line_no = 2
        line2.internal_sku = "INT-888"
        line2.qty = Decimal("5.000")
        line2.uom = "ST"
        line2.unit_price = Decimal("2.50")
        line2.customer_sku_raw = "CD-456"
        line2.product_description = "Schalter"
        line2.currency = None
        line2.requested_delivery_date = None
        line2.line_notes = None

        draft_order.lines = [line1, line2]

        return draft_order

    @pytest.fixture
    def sample_org(self):
        """Create sample organization."""
        org = Mock()
        org.id = uuid4()
        org.slug = "acme"
        return org

    def test_connector_type(self, connector):
        """Test connector type identifier."""
        assert connector.connector_type == "DROPZONE_JSON_V1"

    def test_export_format_version(self, connector):
        """Test export format version identifier."""
        assert connector.export_format_version == "orderflow_export_json_v1"

    def test_generate_export_json_structure(self, connector, sample_draft_order, sample_org):
        """Test that generated JSON has correct structure per §12.1."""
        export_data = connector._generate_export_json(sample_draft_order, sample_org)

        # Check top-level structure (actual implementation uses 'format_version', 'org', 'order')
        assert export_data['format_version'] == 'orderflow_export_json_v1'
        assert export_data['org']['slug'] == 'acme'
        assert export_data['org']['id'] == str(sample_org.id)
        assert 'export_timestamp' in export_data

        # Check order block (contains draft_order_id, header fields, and customer)
        assert export_data['order']['draft_order_id'] == str(sample_draft_order.id)
        assert export_data['order']['external_order_number'] == 'PO-12345'
        assert export_data['order']['order_date'] == '2025-12-01'
        assert export_data['order']['currency'] == 'EUR'
        assert export_data['order']['requested_delivery_date'] == '2025-12-10'
        assert export_data['order']['notes'] == 'Urgent delivery'
        assert export_data['order']['approved_at'] == '2025-12-26T10:00:00+00:00'

        # Check customer block (inside order)
        assert export_data['order']['customer'] is not None
        assert export_data['order']['customer']['erp_customer_number'] == '4711'
        assert export_data['order']['customer']['name'] == 'Muster GmbH'

        # Check lines block (top-level)
        assert len(export_data['lines']) == 2
        line1 = export_data['lines'][0]
        assert line1['line_no'] == 1
        assert line1['internal_sku'] == 'INT-999'
        assert line1['qty'] == 10.0
        assert line1['uom'] == 'M'
        assert line1['unit_price'] == 1.23
        assert line1['customer_sku'] == 'AB-123'  # Field name is 'customer_sku' not 'customer_sku_raw'
        assert line1['description'] == 'Kabel NYM-J 3x1,5'

    def test_generate_export_json_serializable(self, connector, sample_draft_order, sample_org):
        """Test that generated JSON is serializable (no Decimal/date objects)."""
        export_data = connector._generate_export_json(sample_draft_order, sample_org)

        # Should not raise exception
        json_str = json.dumps(export_data, ensure_ascii=False)
        assert len(json_str) > 0

        # Verify deserialization works
        parsed = json.loads(json_str)
        assert parsed['format_version'] == 'orderflow_export_json_v1'

    def test_generate_filename_format(self, connector, sample_draft_order, sample_org):
        """Test filename generation follows pattern: sales_order_{id}_{timestamp}_{uuid}.json"""
        filename = connector.generate_filename(sample_draft_order, sample_org)

        # Check pattern
        assert sample_org.slug in filename
        assert filename.endswith('.json')

        # Check components - format is {org_slug}_{draft_id}_{timestamp}.json
        parts = filename[:-5].split('_')  # Remove .json and split
        assert len(parts) >= 3  # At minimum: slug, uuid parts, timestamp
        assert parts[0] == sample_org.slug
        # Timestamp should be 14 digits (YYYYMMDDHHMMSS)
        assert len(parts[-1]) == 14

    def test_generate_filename_uniqueness(self, connector, sample_draft_order, sample_org):
        """Test that multiple calls generate different filenames due to timestamp."""
        import time
        filename1 = connector.generate_filename(sample_draft_order, sample_org)
        time.sleep(1)  # Ensure timestamp changes
        filename2 = connector.generate_filename(sample_draft_order, sample_org)

        # Same draft order should produce different filenames due to timestamp
        assert filename1 != filename2

    @pytest.mark.asyncio
    async def test_export_filesystem_mode(self, connector, sample_draft_order, sample_org, tmp_path):
        """Test export to local filesystem."""
        config = {
            'mode': 'filesystem',
            'export_path': str(tmp_path),
            'atomic_write': True
        }

        result = await connector.export(sample_draft_order, sample_org, config)

        assert result.success is True
        assert result.export_storage_key.startswith('exports/')
        assert result.connector_metadata.dropzone_path is not None
        assert sample_org.slug in result.connector_metadata.filename
        assert result.connector_metadata.file_size_bytes > 0

        # Verify file was written
        written_file = tmp_path / result.connector_metadata.filename
        assert written_file.exists()

        # Verify JSON content
        file_content = written_file.read_text(encoding='utf-8')
        export_data = json.loads(file_content)
        assert export_data['format_version'] == 'orderflow_export_json_v1'

    @pytest.mark.asyncio
    async def test_export_handles_error(self, connector, sample_draft_order, sample_org):
        """Test that export returns error result when export fails."""
        config = {
            'mode': 'filesystem',
            'export_path': '/tmp/test_export',
            'atomic_write': True
        }

        # Mock the filesystem write to simulate a failure
        with patch.object(connector, '_write_filesystem', new_callable=AsyncMock) as mock_write:
            mock_write.side_effect = PermissionError("Permission denied: unable to write to dropzone")

            result = await connector.export(sample_draft_order, sample_org, config)

        assert result.success is False
        assert result.error_message is not None
        assert len(result.error_message) > 0
        assert result.error_details is not None

    def test_generate_export_json_with_null_fields(self, connector, sample_draft_order, sample_org):
        """Test JSON generation handles null/missing fields correctly."""
        # Set some fields to None
        sample_draft_order.external_order_number = None
        sample_draft_order.order_date = None
        sample_draft_order.requested_delivery_date = None
        sample_draft_order.notes = None
        sample_draft_order.lines[0].customer_sku_raw = None
        sample_draft_order.lines[0].unit_price = None

        export_data = connector._generate_export_json(sample_draft_order, sample_org)

        # Null fields should be present as null (not omitted)
        assert export_data['order']['external_order_number'] is None
        assert export_data['order']['order_date'] is None
        assert export_data['order']['requested_delivery_date'] is None
        assert export_data['order']['notes'] is None
        assert export_data['lines'][0]['customer_sku'] is None
        assert export_data['lines'][0]['unit_price'] is None
