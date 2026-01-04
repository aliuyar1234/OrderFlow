"""DropzoneJsonV1 Connector - JSON export to filesystem/SFTP dropzone.

Exports draft orders as JSON files to a designated dropzone directory,
supporting both local filesystem and SFTP delivery methods.

SSOT Reference: §12.1 (JSON schema), §3.5 (ERPConnectorPort)
"""

import json
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import hashlib

from domain.connectors.ports.erp_connector_port import (
    ERPConnectorPort,
    ExportResult,
    ConnectorMetadata,
)


class DecimalJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and UUID types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class DropzoneJsonV1Connector(ERPConnectorPort):
    """Exports draft orders as JSON to filesystem/SFTP dropzone.

    Generates ORDERFLOW_JSON_V1 format files with naming convention:
    {org_slug}_{draft_id}_{timestamp}.json

    Supports:
    - Local filesystem writes (mode='filesystem')
    - SFTP delivery (mode='sftp')
    - Atomic writes via .tmp suffix + rename
    - Object storage archive of all exports

    Configuration:
        {
            "mode": "filesystem" | "sftp",
            "export_path": "/path/to/dropzone",
            "host": "sftp.example.com",  # For SFTP mode
            "port": 22,                   # For SFTP mode
            "username": "export_user",    # For SFTP mode
            "password": "...",            # For SFTP mode (or use ssh_key)
            "ssh_key": "...",             # For SFTP mode (alternative to password)
            "atomic_write": true,         # Write to .tmp, then rename
            "ack_path": "/path/to/acks"   # Optional path for ack files
        }
    """

    def __init__(self, storage_port: Any = None):
        """Initialize connector with optional storage port.

        Args:
            storage_port: Object storage port for archiving exports
        """
        self._storage_port = storage_port

    @property
    def connector_type(self) -> str:
        """Return connector type identifier."""
        return "DROPZONE_JSON_V1"

    @property
    def export_format_version(self) -> str:
        """Return export format version."""
        return "orderflow_export_json_v1"

    async def export(
        self,
        draft_order: Any,
        org: Any,
        config: dict
    ) -> ExportResult:
        """Export draft order as JSON to dropzone.

        Args:
            draft_order: DraftOrder with lines and customer
            org: Organization entity
            config: Connector configuration

        Returns:
            ExportResult with success status and metadata
        """
        try:
            # Generate export JSON
            export_data = self._generate_export_json(draft_order, org)
            json_bytes = json.dumps(
                export_data,
                cls=DecimalJSONEncoder,
                indent=2,
                ensure_ascii=False
            ).encode('utf-8')

            # Generate filename
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            filename = f"{org.slug}_{draft_order.id}_{timestamp}.json"

            # Store in object storage (archive)
            storage_key = f"exports/{org.id}/{filename}"
            if self._storage_port:
                await self._storage_port.store_file(
                    key=storage_key,
                    data=json_bytes,
                    content_type='application/json'
                )

            # Write to dropzone
            export_path = config.get('export_path', '/tmp/dropzone')
            dropzone_path = f"{export_path}/{filename}"
            mode = config.get('mode', 'filesystem')

            if mode == 'filesystem':
                await self._write_filesystem(
                    json_bytes,
                    dropzone_path,
                    atomic=config.get('atomic_write', True)
                )
            elif mode == 'sftp':
                await self._write_sftp(
                    json_bytes,
                    dropzone_path,
                    config,
                    atomic=config.get('atomic_write', True)
                )
            else:
                raise ValueError(f"Unsupported mode: {mode}")

            return ExportResult(
                success=True,
                export_storage_key=storage_key,
                connector_metadata=ConnectorMetadata(
                    dropzone_path=dropzone_path,
                    filename=filename,
                    file_size_bytes=len(json_bytes),
                    custom={
                        'format_version': self.export_format_version,
                        'mode': mode
                    }
                )
            )

        except Exception as e:
            return ExportResult(
                success=False,
                export_storage_key='',
                error_message=str(e),
                error_details={'exception_type': type(e).__name__}
            )

    def _generate_export_json(self, draft_order: Any, org: Any) -> dict:
        """Generate JSON export structure per SSOT §12.1 schema.

        Args:
            draft_order: DraftOrder with lines
            org: Organization

        Returns:
            Export dictionary matching ORDERFLOW_JSON_V1 schema
        """
        lines = []
        for line in getattr(draft_order, 'lines', []):
            line_data = {
                'line_no': getattr(line, 'line_no', None),
                'internal_sku': getattr(line, 'internal_sku', None),
                'customer_sku': getattr(line, 'customer_sku_raw', None),
                'description': getattr(line, 'product_description', None),
                'qty': float(line.qty) if getattr(line, 'qty', None) else None,
                'uom': getattr(line, 'uom', None),
                'unit_price': float(line.unit_price) if getattr(line, 'unit_price', None) else None,
                'currency': getattr(line, 'currency', None),
                'requested_delivery_date': (
                    line.requested_delivery_date.isoformat()
                    if getattr(line, 'requested_delivery_date', None) else None
                ),
                'line_notes': getattr(line, 'line_notes', None)
            }
            lines.append(line_data)

        # Get customer info if available
        customer = getattr(draft_order, 'customer', None)
        customer_data = None
        if customer:
            customer_data = {
                'erp_customer_number': getattr(customer, 'erp_customer_number', None),
                'name': getattr(customer, 'name', None)
            }

        export = {
            'format_version': self.export_format_version,
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'org': {
                'id': str(org.id),
                'slug': getattr(org, 'slug', None)
            },
            'order': {
                'draft_order_id': str(draft_order.id),
                'external_order_number': getattr(draft_order, 'external_order_number', None),
                'order_date': (
                    draft_order.order_date.isoformat()
                    if getattr(draft_order, 'order_date', None) else None
                ),
                'currency': getattr(draft_order, 'currency', None),
                'requested_delivery_date': (
                    draft_order.requested_delivery_date.isoformat()
                    if getattr(draft_order, 'requested_delivery_date', None) else None
                ),
                'notes': getattr(draft_order, 'notes', None),
                'ship_to': getattr(draft_order, 'ship_to_json', None),
                'bill_to': getattr(draft_order, 'bill_to_json', None),
                'approved_at': (
                    draft_order.approved_at.isoformat()
                    if getattr(draft_order, 'approved_at', None) else None
                ),
                'customer': customer_data
            },
            'lines': lines
        }

        return export

    async def _write_filesystem(
        self,
        data: bytes,
        path: str,
        atomic: bool = True
    ) -> None:
        """Write to local filesystem.

        Args:
            data: Bytes to write
            path: Destination path
            atomic: If True, write to .tmp then rename
        """
        import os

        def _write():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if atomic:
                tmp_path = f"{path}.tmp"
                with open(tmp_path, 'wb') as f:
                    f.write(data)
                os.rename(tmp_path, path)
            else:
                with open(path, 'wb') as f:
                    f.write(data)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write)

    async def _write_sftp(
        self,
        data: bytes,
        path: str,
        config: dict,
        atomic: bool = True
    ) -> None:
        """Write to SFTP server.

        Args:
            data: Bytes to write
            path: Destination path on SFTP server
            config: SFTP connection config
            atomic: If True, write to .tmp then rename
        """
        # Import optional SFTP dependency
        try:
            import paramiko
        except ImportError:
            raise ImportError(
                "paramiko is required for SFTP mode. "
                "Install with: pip install paramiko"
            )

        def _write():
            transport = paramiko.Transport((config['host'], config.get('port', 22)))

            if 'ssh_key' in config:
                # Use SSH key authentication
                key = paramiko.RSAKey.from_private_key_file(config['ssh_key'])
                transport.connect(username=config['username'], pkey=key)
            else:
                # Use password authentication
                transport.connect(
                    username=config['username'],
                    password=config['password']
                )

            sftp = paramiko.SFTPClient.from_transport(transport)

            try:
                # Ensure directory exists
                remote_dir = '/'.join(path.split('/')[:-1])
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    sftp.mkdir(remote_dir)

                if atomic:
                    tmp_path = f"{path}.tmp"
                    with sftp.file(tmp_path, 'wb') as f:
                        f.write(data)
                    sftp.rename(tmp_path, path)
                else:
                    with sftp.file(path, 'wb') as f:
                        f.write(data)
            finally:
                sftp.close()
                transport.close()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write)

    def generate_filename(self, draft_order: Any, org: Any) -> str:
        """Generate export filename.

        Format: {org_slug}_{draft_id}_{timestamp}.json

        Args:
            draft_order: DraftOrder entity
            org: Organization entity

        Returns:
            Generated filename string
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        return f"{org.slug}_{draft_order.id}_{timestamp}.json"
