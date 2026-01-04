"""
Connector implementations

This package contains concrete implementations of ERPConnectorPort.
Each connector handles a specific ERP integration method.
"""

from .mock_connector import MockConnector

__all__ = ["MockConnector"]
