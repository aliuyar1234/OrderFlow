"""ERP Connector Port - Domain interface for ERP export operations.

This port defines the contract for exporting draft orders to ERP systems.
Adapters must implement this interface to provide different export mechanisms
(dropzone, API, etc.).

SSOT Reference: §3.5 (ERPConnectorPort), §12 (DROPZONE_JSON_V1)
Architecture: Hexagonal - Port interface in domain layer
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID


@dataclass
class ConnectorMetadata:
    """Metadata returned by connector about the export operation.

    This flexible structure allows connectors to store implementation-specific
    details without coupling the port interface to specific connector types.

    Attributes:
        dropzone_path: Path where file was written (SFTP/filesystem)
        filename: Generated filename for the export
        file_size_bytes: Size of exported file in bytes
        custom: Any additional connector-specific metadata
    """
    dropzone_path: Optional[str] = None
    filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    custom: dict = field(default_factory=dict)


@dataclass
class ExportResult:
    """Result of an ERP export operation.

    This is the standard return type for all ERP connectors, providing
    consistent information about export success/failure regardless of
    the underlying connector implementation.

    Attributes:
        success: True if export completed successfully
        export_storage_key: S3/MinIO key where export JSON is stored
        connector_metadata: Connector-specific metadata (e.g., dropzone path)
        error_message: Human-readable error if export failed
        error_details: Detailed error information for debugging
    """
    success: bool
    export_storage_key: str
    connector_metadata: ConnectorMetadata = field(default_factory=ConnectorMetadata)
    error_message: Optional[str] = None
    error_details: Optional[dict] = None


class ERPConnectorPort(ABC):
    """Port interface for ERP export operations.

    This interface defines the contract for exporting draft orders to ERP systems.
    Implementations provide different export mechanisms (dropzone, direct API, etc.).

    Key Design Principles:
    - Connector implementations are stateless (config passed per-call or at init)
    - Export operations are idempotent (can retry safely)
    - All connector-specific logic is isolated in adapters
    - Export result includes storage key + connector metadata

    Example Implementations:
    - DropzoneJsonV1Connector: Exports JSON to SFTP/filesystem dropzone
    - DirectAPIConnector (future): Calls ERP REST API directly
    - SAPConnectorV2 (future): Uses SAP-specific integration

    Example Usage:
        connector = DropzoneJsonV1Connector(config, storage_port)

        result = await connector.export(
            draft_order=draft,
            org=org,
            config=connector_config
        )

        if result.success:
            # Store export record with result.export_storage_key
            # and result.connector_metadata.dropzone_path
            pass
        else:
            # Handle error: result.error_message
            pass
    """

    @abstractmethod
    async def export(
        self,
        draft_order: Any,
        org: Any,
        config: dict
    ) -> ExportResult:
        """Export a draft order to ERP system.

        This method:
        1. Generates export data (format depends on connector type)
        2. Stores export file in object storage (S3/MinIO)
        3. Writes export to configured destination (dropzone, API, etc.)
        4. Returns result with storage key and metadata

        Args:
            draft_order: DraftOrder entity with:
                - id: UUID
                - org_id: UUID
                - customer: Customer with erp_customer_number, name
                - lines: List of DraftOrderLine
                - approved_at: Timestamp
                - external_order_number: Customer's PO number
                - order_date, currency, notes, etc.
            org: Organization entity with:
                - id: UUID
                - slug: Organization identifier
            config: Connector configuration dict (format varies by connector):
                For DROPZONE_JSON_V1:
                  - mode: 'sftp' or 'filesystem'
                  - export_path: Target directory
                  - host, port, username, password/ssh_key (if SFTP)
                  - atomic_write: bool (default True)
                  - ack_path: Optional path for acknowledgment files

        Returns:
            ExportResult with:
              - success: True if export succeeded
              - export_storage_key: S3 key where export JSON is stored
              - connector_metadata: Connector-specific info (dropzone path, etc.)
              - error_message/error_details: If export failed

        Raises:
            Should not raise - all errors should be caught and returned
            in ExportResult.error_message/error_details for proper tracking.

        Note:
            - Operation must be idempotent (safe to retry on failure)
            - Storage key format: exports/{org_id}/{filename}
            - Filename format varies by connector (see connector docs)
        """
        pass

    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Connector type identifier.

        This identifies which connector implementation is in use.
        Format: UPPERCASE_WITH_UNDERSCORES

        Examples:
            - DROPZONE_JSON_V1
            - DIRECT_API_V1
            - SAP_IDOC_V1

        Returns:
            Connector type string (stored in erp_connection.connector_type)
        """
        pass

    @property
    @abstractmethod
    def export_format_version(self) -> str:
        """Export format version identifier.

        This identifies the schema/format of the exported data.
        Used for tracking compatibility and schema evolution.

        Examples:
            - orderflow_export_json_v1
            - sap_idoc_orders_v2

        Returns:
            Format version string (stored in erp_export.export_format_version)
        """
        pass
