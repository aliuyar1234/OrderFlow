"""
Push Orchestrator Service - Coordinates ERP push operations

Handles the complete push workflow:
- Idempotency checking
- Connector resolution
- Push execution
- Retry logic with exponential backoff
- Logging and error handling

SSOT Reference: §8 (Approve & Push flow)
"""

import logging
import hashlib
import time
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from .ports import ERPConnectorPort, ExportResult, ConnectorError
from .registry import ConnectorRegistry
from .encryption import EncryptionService, EncryptionError
from models import ERPConnection, ERPPushLog


logger = logging.getLogger(__name__)


class PushServiceError(Exception):
    """Raised when push service operations fail."""
    pass


class PushOrchestrator:
    """
    Orchestrates ERP push operations with idempotency and retry logic.

    Responsibilities:
    - Generate idempotency keys
    - Check for duplicate push attempts
    - Resolve and configure connectors
    - Execute push with retry logic
    - Log all attempts for debugging and audit

    Usage:
        orchestrator = PushOrchestrator(db_session)
        result = orchestrator.push_order(
            org_id=org.id,
            draft_order=draft_order,
            max_retries=3
        )
    """

    def __init__(self, db: Session):
        """
        Initialize push orchestrator.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def generate_idempotency_key(
        self,
        org_id: UUID,
        draft_order_id: UUID,
        attempt_number: int = 0
    ) -> str:
        """
        Generate a unique idempotency key for a push attempt.

        The key is deterministic based on org_id + draft_order_id + attempt,
        so retrying the same order produces the same key.

        Args:
            org_id: Organization ID
            draft_order_id: Draft order ID
            attempt_number: Attempt number (0 for first try, 1+ for retries)

        Returns:
            Idempotency key (hex string)

        Example:
            key = orchestrator.generate_idempotency_key(org_id, order_id, 0)
            # "a7b3c4d5e6f7..."
        """
        data = f"{org_id}:{draft_order_id}:{attempt_number}".encode('utf-8')
        return hashlib.sha256(data).hexdigest()

    def check_idempotency(self, idempotency_key: str) -> Optional[ERPPushLog]:
        """
        Check if a push with this idempotency key already exists.

        Args:
            idempotency_key: The idempotency key to check

        Returns:
            Existing ERPPushLog if found, None otherwise
        """
        return self.db.query(ERPPushLog).filter(
            ERPPushLog.idempotency_key == idempotency_key
        ).first()

    def get_active_connector(self, org_id: UUID) -> Optional[ERPConnection]:
        """
        Get the active ERP connection for an organization.

        Args:
            org_id: Organization ID

        Returns:
            Active ERPConnection if found, None otherwise
        """
        return self.db.query(ERPConnection).filter(
            ERPConnection.org_id == org_id,
            ERPConnection.status == 'ACTIVE'
        ).first()

    def push_order(
        self,
        org_id: UUID,
        draft_order: Any,
        max_retries: int = 3,
        retry_delay_base: float = 1.0
    ) -> ERPPushLog:
        """
        Push a draft order to ERP with idempotency and retry logic.

        Args:
            org_id: Organization ID
            draft_order: DraftOrder to push
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay_base: Base delay in seconds for exponential backoff (default: 1.0)

        Returns:
            ERPPushLog with push result

        Raises:
            PushServiceError: If no active connector or push fails after all retries

        Example:
            result = orchestrator.push_order(
                org_id=org.id,
                draft_order=draft_order,
                max_retries=3
            )
            if result.status == "SUCCESS":
                print("Order pushed successfully!")
        """
        # Get active connector
        connection = self.get_active_connector(org_id)
        if not connection:
            raise PushServiceError(
                f"No active ERP connector configured for org {org_id}"
            )

        # Decrypt connector configuration
        try:
            config = EncryptionService.decrypt_config(connection.config_encrypted)
        except EncryptionError as e:
            logger.error(f"Failed to decrypt connector config: {e}")
            raise PushServiceError(f"Failed to decrypt connector configuration: {e}")

        # Resolve connector implementation
        try:
            connector = ConnectorRegistry.get(connection.connector_type)
        except ValueError as e:
            logger.error(f"Failed to resolve connector: {e}")
            raise PushServiceError(f"Unknown connector type: {connection.connector_type}")

        # Push with retry logic
        return self._push_with_retry(
            org_id=org_id,
            draft_order=draft_order,
            connector=connector,
            connector_type=connection.connector_type,
            config=config,
            max_retries=max_retries,
            retry_delay_base=retry_delay_base
        )

    def _push_with_retry(
        self,
        org_id: UUID,
        draft_order: Any,
        connector: ERPConnectorPort,
        connector_type: str,
        config: Dict[str, Any],
        max_retries: int,
        retry_delay_base: float
    ) -> ERPPushLog:
        """
        Execute push with exponential backoff retry logic.

        Args:
            org_id: Organization ID
            draft_order: DraftOrder to push
            connector: Connector instance
            connector_type: Connector type string
            config: Decrypted connector configuration
            max_retries: Maximum retry attempts
            retry_delay_base: Base delay for exponential backoff

        Returns:
            ERPPushLog with final result
        """
        last_error = None
        last_log = None

        for attempt in range(max_retries + 1):
            # Generate idempotency key for this attempt
            idempotency_key = self.generate_idempotency_key(
                org_id=org_id,
                draft_order_id=draft_order.id,
                attempt_number=attempt
            )

            # Check idempotency (skip if already processed)
            existing_log = self.check_idempotency(idempotency_key)
            if existing_log:
                logger.info(
                    f"Push already processed (idempotency): {idempotency_key}"
                )
                return existing_log

            # Create push log entry
            push_log = ERPPushLog(
                org_id=org_id,
                draft_order_id=draft_order.id,
                connector_type=connector_type,
                status='PENDING' if attempt == 0 else 'RETRYING',
                idempotency_key=idempotency_key,
                retry_count=attempt
            )
            self.db.add(push_log)
            self.db.flush()  # Get ID without committing

            # Execute push
            start_time = time.time()
            try:
                result = connector.export(draft_order, config)
                latency_ms = int((time.time() - start_time) * 1000)

                # Update push log with success
                push_log.status = 'SUCCESS'
                push_log.response_json = result.connector_metadata
                push_log.latency_ms = latency_ms
                self.db.commit()

                logger.info(
                    f"Push succeeded on attempt {attempt + 1}",
                    extra={
                        "draft_order_id": str(draft_order.id),
                        "connector_type": connector_type,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms
                    }
                )

                return push_log

            except ConnectorError as e:
                latency_ms = int((time.time() - start_time) * 1000)
                last_error = str(e)

                # Update push log with failure
                push_log.status = 'FAILED'
                push_log.error_message = last_error
                push_log.latency_ms = latency_ms
                self.db.commit()

                last_log = push_log

                logger.warning(
                    f"Push failed on attempt {attempt + 1}: {last_error}",
                    extra={
                        "draft_order_id": str(draft_order.id),
                        "connector_type": connector_type,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms,
                        "error": last_error
                    }
                )

                # Retry with exponential backoff
                if attempt < max_retries:
                    delay = retry_delay_base * (2 ** attempt)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)

        # All retries exhausted
        logger.error(
            f"Push failed after {max_retries + 1} attempts",
            extra={
                "draft_order_id": str(draft_order.id),
                "connector_type": connector_type,
                "final_error": last_error
            }
        )

        return last_log

    def test_connection(self, org_id: UUID) -> Dict[str, Any]:
        """
        Test the active ERP connection for an organization.

        Args:
            org_id: Organization ID

        Returns:
            Test result dictionary with success, error_message, and latency_ms

        Raises:
            PushServiceError: If no active connector
        """
        connection = self.get_active_connector(org_id)
        if not connection:
            raise PushServiceError(
                f"No active ERP connector configured for org {org_id}"
            )

        try:
            config = EncryptionService.decrypt_config(connection.config_encrypted)
        except EncryptionError as e:
            return {
                "success": False,
                "error_message": f"Failed to decrypt configuration: {e}",
                "latency_ms": 0
            }

        try:
            connector = ConnectorRegistry.get(connection.connector_type)
        except ValueError as e:
            return {
                "success": False,
                "error_message": f"Unknown connector type: {connection.connector_type}",
                "latency_ms": 0
            }

        start_time = time.time()
        try:
            result = connector.test_connection(config)
            latency_ms = int((time.time() - start_time) * 1000)

            # Update last_test_at on success
            if result.success:
                connection.last_test_at = datetime.utcnow()
                self.db.commit()

            return {
                "success": result.success,
                "error_message": result.error_message,
                "latency_ms": latency_ms
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error_message": f"Test failed: {e}",
                "latency_ms": latency_ms
            }
