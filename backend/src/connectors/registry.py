"""
Connector Registry - Central registration and resolution of ERP connectors

The ConnectorRegistry maintains a mapping of connector_type strings to
implementation classes, enabling runtime resolution without tight coupling.

SSOT Reference: Spec §3.5 (Connector Registry)
"""

from typing import Dict, Type
from .ports import ERPConnectorPort


class ConnectorRegistry:
    """
    Registry for ERP connector implementations.

    Provides a centralized mechanism for registering and resolving connectors.
    Domain logic uses this to get the appropriate connector based on org configuration.

    Usage:
        # Register a connector (typically at application startup)
        ConnectorRegistry.register("DROPZONE_JSON_V1", DropzoneJsonV1Connector)

        # Get a connector instance at runtime
        connector = ConnectorRegistry.get("DROPZONE_JSON_V1")
        result = connector.export(draft_order, config)

    Thread-safety: Read operations are thread-safe after initial registration.
    Registration should happen only at startup in the main thread.
    """

    _connectors: Dict[str, Type[ERPConnectorPort]] = {}

    @classmethod
    def register(cls, connector_type: str, implementation: Type[ERPConnectorPort]) -> None:
        """
        Register a connector implementation.

        Args:
            connector_type: Unique identifier for the connector (e.g., 'DROPZONE_JSON_V1')
            implementation: Class implementing ERPConnectorPort

        Raises:
            ValueError: If connector_type is empty or implementation doesn't inherit from ERPConnectorPort
            RuntimeError: If connector_type is already registered (prevents accidental override)

        Example:
            ConnectorRegistry.register("DROPZONE_JSON_V1", DropzoneJsonV1Connector)
        """
        if not connector_type or not connector_type.strip():
            raise ValueError("connector_type cannot be empty")

        if not issubclass(implementation, ERPConnectorPort):
            raise ValueError(
                f"Implementation must inherit from ERPConnectorPort, "
                f"got {implementation.__name__}"
            )

        if connector_type in cls._connectors:
            raise RuntimeError(
                f"Connector type '{connector_type}' is already registered. "
                f"Use unregister() first if you need to replace it."
            )

        cls._connectors[connector_type] = implementation

    @classmethod
    def get(cls, connector_type: str) -> ERPConnectorPort:
        """
        Get a connector instance by type.

        Args:
            connector_type: The connector type to retrieve

        Returns:
            A new instance of the connector implementation

        Raises:
            ValueError: If connector_type is not registered

        Example:
            connector = ConnectorRegistry.get("DROPZONE_JSON_V1")
            result = connector.export(draft_order, config)
        """
        if connector_type not in cls._connectors:
            available = ', '.join(cls._connectors.keys()) if cls._connectors else 'none'
            raise ValueError(
                f"Unknown connector type: '{connector_type}'. "
                f"Available connectors: {available}"
            )

        implementation_class = cls._connectors[connector_type]
        return implementation_class()

    @classmethod
    def list_available(cls) -> list[str]:
        """
        List all registered connector types.

        Returns:
            List of registered connector type strings

        Example:
            >>> ConnectorRegistry.list_available()
            ['DROPZONE_JSON_V1', 'MOCK', 'SAP']
        """
        return sorted(cls._connectors.keys())

    @classmethod
    def is_registered(cls, connector_type: str) -> bool:
        """
        Check if a connector type is registered.

        Args:
            connector_type: The connector type to check

        Returns:
            True if registered, False otherwise

        Example:
            if ConnectorRegistry.is_registered("DROPZONE_JSON_V1"):
                connector = ConnectorRegistry.get("DROPZONE_JSON_V1")
        """
        return connector_type in cls._connectors

    @classmethod
    def unregister(cls, connector_type: str) -> None:
        """
        Remove a connector from the registry.

        Primarily used for testing. In production, connectors should remain
        registered for the lifetime of the application.

        Args:
            connector_type: The connector type to unregister

        Raises:
            ValueError: If connector_type is not registered
        """
        if connector_type not in cls._connectors:
            raise ValueError(f"Connector type '{connector_type}' is not registered")

        del cls._connectors[connector_type]

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered connectors.

        WARNING: This should only be used in tests. In production, clearing
        the registry will break all connector resolution.
        """
        cls._connectors.clear()
