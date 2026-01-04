"""ERP Connector Implementations - Infrastructure Layer.

Connector implementations that integrate with external ERP systems.
These are infrastructure concerns and depend on domain ports.

Architecture:
- Domain layer defines ports (interfaces): domain.connectors.ports
- Infrastructure layer provides implementations: infrastructure.connectors
"""

from .dropzone_json_v1 import DropzoneJsonV1Connector

__all__ = ["DropzoneJsonV1Connector"]
