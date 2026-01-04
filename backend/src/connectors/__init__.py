"""
Connectors module - ERP integration framework

This module provides a plugin architecture for integrating with diverse ERP systems
through a standard Port interface (ERPConnectorPort). The framework handles:
- Secure credential storage via AES-256-GCM encryption
- Connection testing without live exports
- Connector registration/resolution through ConnectorRegistry
- Push orchestration with idempotency and retry logic

SSOT References: §3.5 (ERPConnectorPort), §5.4.14 (erp_connection), §8.9 (Connectors API)
"""

from .ports import ERPConnectorPort, ExportResult, TestResult, ConnectorError
from .registry import ConnectorRegistry
from .encryption import EncryptionService, EncryptionError
from .push_service import PushOrchestrator, PushServiceError
from .base_connector import BaseConnector

__all__ = [
    "ERPConnectorPort",
    "ExportResult",
    "TestResult",
    "ConnectorError",
    "ConnectorRegistry",
    "EncryptionService",
    "EncryptionError",
    "PushOrchestrator",
    "PushServiceError",
    "BaseConnector",
]
