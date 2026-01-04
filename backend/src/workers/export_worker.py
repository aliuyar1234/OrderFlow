"""ERP Export Worker - Background job for pushing draft orders to ERP.

Processes ERPExport records by invoking the configured connector to generate
and deliver export files to the ERP dropzone or API.

SSOT Reference: §6.5 (Push Rules), §12 (Export Format)
"""

from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID
import traceback

from celery import shared_task
from sqlalchemy.orm import Session

from .base import BaseTask, validate_org_id, get_scoped_session
from models.draft_order import DraftOrder
from models.erp_export import ERPExport, ERPExportStatus
from models.erp_connection import ERPConnection
from models.org import Org
from draft_orders.status import DraftOrderStatus
from audit.service import log_audit_event
from domain.connectors.ports.erp_connector_port import ERPConnectorPort
from infrastructure.encryption import decrypt_config


# Connector registry (to be populated by infrastructure layer)
# Maps connector_type -> ERPConnectorPort implementation
CONNECTOR_REGISTRY: Dict[str, ERPConnectorPort] = {}


def register_connector(connector_type: str, connector: ERPConnectorPort) -> None:
    """Register a connector implementation.

    Args:
        connector_type: Connector type identifier (e.g., 'DROPZONE_JSON_V1')
        connector: Connector implementation instance

    Example:
        from infrastructure.connectors.dropzone_json_v1 import DropzoneJsonV1Connector
        register_connector('DROPZONE_JSON_V1', DropzoneJsonV1Connector())
    """
    CONNECTOR_REGISTRY[connector_type] = connector


def get_connector(connector_type: str) -> ERPConnectorPort:
    """Get connector implementation by type.

    Args:
        connector_type: Connector type identifier

    Returns:
        ERPConnectorPort: Connector implementation

    Raises:
        ValueError: If connector type not registered
    """
    connector = CONNECTOR_REGISTRY.get(connector_type)
    if not connector:
        raise ValueError(
            f"Connector type '{connector_type}' not registered. "
            f"Available types: {list(CONNECTOR_REGISTRY.keys())}"
        )
    return connector


@shared_task(base=BaseTask, bind=True, max_retries=3)
def process_erp_export(
    self,
    export_id: str,
    org_id: str
) -> Dict[str, Any]:
    """Process an ERP export job.

    Fetches export record, loads connector, generates export, and updates status.
    Retries on transient failures (network errors, SFTP timeout, etc.).

    Args:
        export_id: UUID string of ERPExport record
        org_id: UUID string of organization (REQUIRED for tenant isolation)

    Returns:
        Dict with processing result:
            - status: 'success' or 'failed'
            - export_id: Export ID
            - draft_order_id: Draft order ID
            - export_storage_key: S3 key (if successful)
            - dropzone_path: Dropzone path (if successful)
            - error: Error message (if failed)

    SSOT Reference: §6.5 (FR-012 to FR-016)

    Example:
        # Enqueue from API endpoint
        from .workers.export_worker import process_erp_export
        process_erp_export.delay(
            export_id=str(export.id),
            org_id=str(org.id)
        )
    """
    # Validate org_id (automatic via BaseTask, but explicit for clarity)
    org_uuid = validate_org_id(org_id)
    export_uuid = UUID(export_id)

    # Get scoped session
    session = get_scoped_session(org_uuid)

    try:
        # Fetch export record with explicit org_id filter
        export = session.query(ERPExport).filter(
            ERPExport.id == export_uuid,
            ERPExport.org_id == org_uuid
        ).first()

        if not export:
            raise ValueError(f"ERPExport {export_id} not found in org {org_id}")

        # Fetch draft order
        draft = session.query(DraftOrder).filter(
            DraftOrder.id == export.draft_order_id,
            DraftOrder.org_id == org_uuid
        ).first()

        if not draft:
            raise ValueError(f"DraftOrder {export.draft_order_id} not found")

        # Fetch organization
        org = session.query(Org).filter(Org.id == org_uuid).first()
        if not org:
            raise ValueError(f"Organization {org_id} not found")

        # Fetch ERP connection
        connection = session.query(ERPConnection).filter(
            ERPConnection.id == export.erp_connection_id,
            ERPConnection.org_id == org_uuid
        ).first()

        if not connection:
            raise ValueError(f"ERPConnection {export.erp_connection_id} not found")

        # Get connector implementation (SSOT §6.5 FR-013)
        connector = get_connector(connection.connector_type)

        # Decrypt configuration using AES-256-GCM
        config = decrypt_config(connection.config_encrypted)

        # Execute export (SSOT §6.5 FR-013)
        # Note: Connector.export is async, need to handle properly
        import asyncio
        result = asyncio.run(connector.export(
            draft_order=draft,
            org=org,
            config=config
        ))

        if result.success:
            # Update export record (SSOT §6.5 FR-014)
            export.status = ERPExportStatus.SENT.value
            export.export_storage_key = result.export_storage_key
            export.dropzone_path = result.connector_metadata.dropzone_path

            # Update draft status (SSOT §6.5 FR-010)
            draft.status = DraftOrderStatus.PUSHED.value

            session.commit()

            return {
                "status": "success",
                "export_id": export_id,
                "draft_order_id": str(draft.id),
                "export_storage_key": result.export_storage_key,
                "dropzone_path": result.connector_metadata.dropzone_path
            }
        else:
            # Export failed (SSOT §6.5 FR-014, FR-016)
            raise Exception(result.error_message or "Export failed")

    except Exception as e:
        # Handle error (SSOT §6.5 FR-016)
        error_details = {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback": traceback.format_exc()
        }

        # Update export status
        if 'export' in locals():
            export.status = ERPExportStatus.FAILED.value
            export.error_json = error_details

        # Update draft status
        if 'draft' in locals():
            draft.status = DraftOrderStatus.ERROR.value

        # Create audit log for failure (SSOT §6.5 FR-016)
        if 'draft' in locals():
            log_audit_event(
                db=session,
                org_id=org_uuid,
                actor_id=None,  # System action
                action="DRAFT_PUSH_FAILED",
                entity_type="draft_order",
                entity_id=draft.id,
                metadata={
                    "draft_id": str(draft.id),
                    "export_id": export_id,
                    "error": str(e)
                }
            )

        session.commit()

        # Retry on transient errors
        if should_retry_error(e):
            # Exponential backoff: 60s, 120s, 240s
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

        return {
            "status": "failed",
            "export_id": export_id,
            "draft_order_id": str(draft.id) if 'draft' in locals() else None,
            "error": str(e)
        }

    finally:
        session.close()


def should_retry_error(error: Exception) -> bool:
    """Determine if error is transient and should be retried.

    Args:
        error: Exception that occurred during export

    Returns:
        bool: True if error should trigger retry, False otherwise

    Retry conditions:
    - Network errors (connection timeout, unreachable)
    - SFTP temporary failures
    - S3/MinIO rate limits

    Do not retry:
    - Validation errors (missing customer, invalid data)
    - Authentication errors (invalid credentials)
    - Schema errors (export format mismatch)
    """
    error_str = str(error).lower()

    # Network/connection errors - retry
    if any(keyword in error_str for keyword in [
        'connection', 'timeout', 'unreachable', 'network',
        'sftp', 'ssh', 'socket'
    ]):
        return True

    # S3/storage errors - retry
    if any(keyword in error_str for keyword in [
        'rate limit', 's3', 'minio', 'storage'
    ]):
        return True

    # Validation/auth errors - do not retry
    if any(keyword in error_str for keyword in [
        'validation', 'invalid', 'authentication', 'permission',
        'not found', 'missing'
    ]):
        return False

    # Default: do not retry unknown errors
    return False


def enqueue_export_job(export_id: UUID, org_id: UUID) -> None:
    """Enqueue an export job for background processing.

    Convenience function to enqueue export jobs from API endpoints.

    Args:
        export_id: ERPExport ID to process
        org_id: Organization ID

    Example:
        from workers.export_worker import enqueue_export_job
        enqueue_export_job(export.id, org.id)
    """
    process_erp_export.delay(
        export_id=str(export_id),
        org_id=str(org_id)
    )
