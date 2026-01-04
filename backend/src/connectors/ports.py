"""
ERPConnectorPort - Port interface for ERP integrations

This module defines the abstract interface that all ERP connectors must implement.
Following hexagonal architecture, domain logic depends only on this Port, not on
concrete implementations (Adapters).

SSOT Reference: §3.5 (ERPConnectorPort)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID
from datetime import datetime


@dataclass
class ExportResult:
    """
    Standard return structure for ERPConnectorPort.export() method.

    All ERPConnectorPort implementations MUST return this exact structure.
    Connector-specific fields go in connector_metadata.

    Attributes:
        success: Whether the export operation succeeded
        export_id: UUID of the created erp_export record
        error_message: Human-readable error message if success=False
        storage_key: Object storage key where export file is stored
        connector_metadata: Connector-specific metadata (e.g., dropzone_path, erp_order_id)
    """
    success: bool
    export_id: UUID
    error_message: Optional[str] = None
    storage_key: Optional[str] = None
    connector_metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.connector_metadata is None:
            self.connector_metadata = {}


@dataclass
class TestResult:
    """
    Result of connector connection test.

    Attributes:
        success: Whether the connection test succeeded
        error_message: Human-readable error message if success=False
        latency_ms: Time taken for the test in milliseconds
        test_timestamp: When the test was performed
    """
    success: bool
    error_message: Optional[str] = None
    latency_ms: int = 0
    test_timestamp: datetime = None

    def __post_init__(self):
        if self.test_timestamp is None:
            self.test_timestamp = datetime.utcnow()


class ConnectorError(Exception):
    """
    Base exception for connector-related errors.

    Raised by connector implementations when export or test operations fail.
    Domain services catch this and handle it gracefully (e.g., set status=FAILED).
    """
    pass


class ERPConnectorPort(ABC):
    """
    Abstract interface for ERP connectors.

    All ERP integration implementations must inherit from this class and implement
    the required methods. This enables:
    - Domain logic independence from specific connector implementations
    - Easy mocking in tests (no real SFTP/API connections needed)
    - Adding new connectors without changing domain code

    Implementations:
    - DropzoneJsonV1Connector: SFTP/filesystem export (MVP)
    - MockConnector: In-memory connector for testing
    - Future: SAPConnector, EDIConnector, RestAPIConnector, etc.

    SSOT Reference: §3.5
    """

    @abstractmethod
    def export(self, draft_order: Any, config: dict) -> ExportResult:
        """
        Export a draft order to the ERP system.

        This method transforms the draft order into the connector's required format,
        transmits it to the ERP system (or dropzone), and returns the result.

        Args:
            draft_order: The DraftOrder domain object to export
            config: Decrypted connector configuration (from erp_connection.config_encrypted)
                   Contains connector-specific settings (host, credentials, paths, etc.)

        Returns:
            ExportResult with success status, storage key, and metadata

        Raises:
            ConnectorError: If export fails (authentication, network, validation, etc.)

        Implementation Requirements:
        - MUST be idempotent (multiple calls with same draft_order produce same result)
        - MUST validate config before attempting export
        - MUST handle network failures gracefully
        - SHOULD include detailed error messages for debugging
        """
        pass

    @abstractmethod
    def test_connection(self, config: dict) -> TestResult:
        """
        Test the ERP connection without exporting a real order.

        This method validates credentials, network connectivity, and permissions
        by performing a minimal operation (e.g., writing and deleting a test file).

        Args:
            config: Decrypted connector configuration to test

        Returns:
            TestResult with success status, latency, and error details

        Raises:
            ConnectorError: If test fails (should be caught and converted to TestResult)

        Implementation Requirements:
        - MUST NOT create any permanent artifacts in ERP
        - SHOULD complete within 5 seconds (timeout)
        - MUST validate all required config fields
        - SHOULD test actual connectivity (not just config validation)
        """
        pass

    def get_connector_type(self) -> str:
        """
        Return the connector type identifier.

        This is used by ConnectorRegistry for registration.
        Defaults to the class name if not overridden.

        Returns:
            Connector type string (e.g., 'DROPZONE_JSON_V1', 'MOCK')
        """
        return self.__class__.__name__.replace("Connector", "").upper()
