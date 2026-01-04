"""Dropzone JSON V1 Connector - exports draft orders as JSON to SFTP/filesystem.

This connector implements the ERPConnectorPort interface for JSON file-based
ERP integration. It generates orderflow_export_json_v1 format files and writes
them to configured dropzone locations (SFTP or local filesystem).

SSOT Reference: §12 (DROPZONE_JSON_V1), §12.1 (JSON schema), §12.2 (Ack mechanism)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
import os

from domain.connectors.ports.erp_connector_port import ERPConnectorPort, ExportResult, ConnectorMetadata
from domain.documents.ports.object_storage_port import ObjectStoragePort

logger = logging.getLogger(__name__)


class DropzoneJsonV1Connector(ERPConnectorPort):
    """Dropzone JSON V1 Connector implementation.

    This connector exports draft orders as JSON files following the
    orderflow_export_json_v1 schema and writes them to SFTP or filesystem
    dropzone locations.

    Features:
    - JSON generation per §12.1 schema
    - Atomic write (.tmp + rename) for SFTP/filesystem
    - Object storage backup of all exports
    - Unique filename generation with timestamp + UUID suffix

    Example:
        storage = S3StorageAdapter(...)
        connector = DropzoneJsonV1Connector(storage)

        config = {
            'mode': 'sftp',
            'host': 'sftp.example.com',
            'username': 'orderflow',
            'password': 'secret',
            'export_path': '/exports',
            'atomic_write': True
        }

        result = await connector.export(draft_order, org, config)
    """

    def __init__(self, object_storage: ObjectStoragePort):
        """Initialize connector with object storage dependency.

        Args:
            object_storage: Object storage port for export file backup
        """
        self._storage = object_storage

    @property
    def connector_type(self) -> str:
        """Connector type identifier."""
        return "DROPZONE_JSON_V1"

    @property
    def export_format_version(self) -> str:
        """Export format version identifier."""
        return "orderflow_export_json_v1"

    async def export(
        self,
        draft_order: Any,
        org: Any,
        config: dict
    ) -> ExportResult:
        """Export draft order to JSON dropzone.

        This method:
        1. Generates export JSON per §12.1 schema
        2. Creates unique filename with timestamp and UUID
        3. Stores JSON in object storage (S3/MinIO)
        4. Writes JSON to dropzone (SFTP or filesystem)
        5. Returns result with storage key and dropzone path

        Args:
            draft_order: DraftOrder entity with all fields populated
            org: Organization entity with slug
            config: Connector configuration:
                - mode: 'sftp' or 'filesystem'
                - export_path: Target directory
                For SFTP mode:
                  - host, port, username, password/ssh_key
                  - atomic_write: bool (default True)

        Returns:
            ExportResult with success status, storage key, and metadata
        """
        try:
            # Generate export JSON
            logger.info(f"Generating export JSON for draft_order_id={draft_order.id}")
            export_data = self._generate_export_json(draft_order, org)
            export_json = json.dumps(export_data, indent=2, ensure_ascii=False)

            # Generate unique filename
            filename = self._generate_filename(draft_order)
            logger.debug(f"Generated filename: {filename}")

            # Store in object storage
            storage_key = f"exports/{org.id}/{filename}"
            logger.info(f"Storing export to object storage: {storage_key}")

            from io import BytesIO
            export_bytes = export_json.encode('utf-8')
            stored_file = await self._storage.store_file(
                file=BytesIO(export_bytes),
                org_id=org.id,
                filename=filename,
                mime_type='application/json'
            )

            # Write to dropzone
            mode = config.get('mode', 'filesystem')
            logger.info(f"Writing to dropzone (mode={mode})")

            if mode == 'sftp':
                dropzone_path = await self._write_to_sftp(filename, export_json, config)
            elif mode == 'filesystem':
                dropzone_path = await self._write_to_filesystem(filename, export_json, config)
            else:
                raise ValueError(f"Unsupported dropzone mode: {mode}")

            logger.info(f"Export completed successfully: {dropzone_path}")

            return ExportResult(
                success=True,
                export_storage_key=stored_file.storage_key,
                connector_metadata=ConnectorMetadata(
                    dropzone_path=dropzone_path,
                    filename=filename,
                    file_size_bytes=len(export_bytes)
                )
            )

        except Exception as e:
            logger.error(f"Export failed for draft_order_id={draft_order.id}: {e}", exc_info=True)
            return ExportResult(
                success=False,
                export_storage_key="",
                error_message=str(e),
                error_details={
                    'exception_type': type(e).__name__,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            )

    def _generate_export_json(self, draft_order: Any, org: Any) -> dict:
        """Generate export JSON per §12.1 schema.

        Args:
            draft_order: DraftOrder entity
            org: Organization entity

        Returns:
            Dict following orderflow_export_json_v1 schema
        """
        # Build customer block
        customer_data = None
        if draft_order.customer_id:
            # Assuming customer relationship is loaded
            customer = draft_order.customer if hasattr(draft_order, 'customer') else None
            if customer:
                customer_data = {
                    "id": str(customer.id),
                    "erp_customer_number": customer.erp_customer_number,
                    "name": customer.name
                }

        # Build header block
        header_data = {
            "external_order_number": draft_order.external_order_number,
            "order_date": draft_order.order_date.isoformat() if draft_order.order_date else None,
            "currency": draft_order.currency,
            "requested_delivery_date": draft_order.requested_delivery_date.isoformat() if draft_order.requested_delivery_date else None,
            "notes": draft_order.notes
        }

        # Build lines block
        lines_data = []
        for line in draft_order.lines:
            line_dict = {
                "line_no": line.line_no,
                "internal_sku": line.internal_sku,
                "qty": float(line.qty) if line.qty else 0.0,
                "uom": line.uom,
                "unit_price": float(line.unit_price) if line.unit_price else None,
                "currency": draft_order.currency,
                "customer_sku_raw": line.customer_sku_raw,
                "description": line.product_description
            }
            lines_data.append(line_dict)

        # Build meta block
        approved_by_email = None
        if draft_order.approved_by_user_id:
            # Assuming approved_by_user relationship is loaded
            approved_by = draft_order.approved_by_user if hasattr(draft_order, 'approved_by_user') else None
            if approved_by:
                approved_by_email = approved_by.email

        source_document_data = None
        if draft_order.document_id:
            # Assuming document relationship is loaded
            document = draft_order.document if hasattr(draft_order, 'document') else None
            if document:
                source_document_data = {
                    "document_id": str(document.id),
                    "file_name": document.file_name,
                    "sha256": document.sha256
                }

        meta_data = {
            "created_by": approved_by_email,
            "source_document": source_document_data
        }

        # Assemble complete export
        export_data = {
            "export_version": self.export_format_version,
            "org_slug": org.slug,
            "draft_order_id": str(draft_order.id),
            "approved_at": draft_order.approved_at.isoformat() if draft_order.approved_at else None,
            "customer": customer_data,
            "header": header_data,
            "lines": lines_data,
            "meta": meta_data
        }

        return export_data

    def _generate_filename(self, draft_order: Any) -> str:
        """Generate unique filename for export.

        Format: sales_order_{draft_id}_{timestamp}_{uuid_short}.json
        Per spec §12.1 with UUID suffix for collision prevention.

        Args:
            draft_order: DraftOrder entity

        Returns:
            Filename string
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        draft_id_short = str(draft_order.id).split('-')[0]  # First segment of UUID
        uuid_suffix = str(uuid4())[:8]  # First 8 chars of random UUID

        filename = f"sales_order_{draft_id_short}_{timestamp}_{uuid_suffix}.json"
        return filename

    async def _write_to_sftp(self, filename: str, content: str, config: dict) -> str:
        """Write export file to SFTP dropzone with atomic rename.

        Args:
            filename: Name of file to write
            content: JSON content as string
            config: SFTP configuration

        Returns:
            Full path where file was written

        Raises:
            Exception: If SFTP write fails
        """
        from infrastructure.sftp import SFTPClient, SFTPConfig, SFTPError

        sftp_config = SFTPConfig(
            host=config['host'],
            port=config.get('port', 22),
            username=config['username'],
            password=config.get('password'),
            ssh_key=config.get('ssh_key'),
            export_path=config['export_path'],
            atomic_write=config.get('atomic_write', True)
        )

        client = SFTPClient(sftp_config)

        try:
            client.connect()
            dropzone_path = client.write_file(filename, content)
            return dropzone_path
        finally:
            client.close()

    async def _write_to_filesystem(self, filename: str, content: str, config: dict) -> str:
        """Write export file to local filesystem with atomic rename.

        Args:
            filename: Name of file to write
            content: JSON content as string
            config: Filesystem configuration with export_path

        Returns:
            Full path where file was written

        Raises:
            Exception: If filesystem write fails
        """
        export_path = Path(config['export_path'])
        export_path.mkdir(parents=True, exist_ok=True)

        atomic_write = config.get('atomic_write', True)
        final_path = export_path / filename

        if atomic_write:
            # Atomic write: .tmp + rename
            tmp_path = export_path / f"{filename}.tmp"

            logger.debug(f"Writing to temporary file: {tmp_path}")
            tmp_path.write_text(content, encoding='utf-8')

            logger.debug(f"Renaming {tmp_path} -> {final_path}")
            tmp_path.rename(final_path)
        else:
            # Direct write
            logger.debug(f"Writing directly to: {final_path}")
            final_path.write_text(content, encoding='utf-8')

        return str(final_path)
