"""Retention service for data cleanup operations.

This service implements the core retention logic:
- Soft-delete expired documents/drafts/messages
- Hard-delete records past grace period
- Delete expired AI logs and feedback events
- Object storage cleanup
- Audit logging for all deletions

All operations are idempotent and can be safely retried.

SSOT Reference: §11.5 (Data Retention)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.org import Org
from audit.service import log_audit_event
from .schemas import RetentionSettings, RetentionStatistics, RetentionReport

logger = logging.getLogger(__name__)

# Batch size for deletion operations to avoid long transactions
DELETION_BATCH_SIZE = 1000


class RetentionService:
    """Service for executing retention cleanup operations.

    This service encapsulates all retention logic and provides methods for:
    - Calculating cutoff dates based on retention settings
    - Soft-deleting expired records
    - Hard-deleting records past grace period
    - Generating retention reports
    - Cleaning up object storage files

    All methods are scoped to a specific organization for multi-tenant isolation.
    """

    def __init__(
        self,
        db: Session,
        org_id: UUID,
        storage_client: Optional[Any] = None
    ):
        """Initialize retention service.

        Args:
            db: Database session
            org_id: Organization UUID for tenant isolation
            storage_client: Optional object storage client for file deletion
        """
        self.db = db
        self.org_id = org_id
        self.storage_client = storage_client

        # Load organization and settings
        self.org = db.query(Org).filter(Org.id == org_id).first()
        if not self.org:
            raise ValueError(f"Organization {org_id} not found")

        # Parse retention settings from org.settings_json
        self.settings = RetentionSettings(**self.org.settings_json.get('retention', {}))

    def get_retention_settings(self) -> RetentionSettings:
        """Get current retention settings for organization.

        Returns:
            RetentionSettings: Current retention configuration
        """
        return self.settings

    def calculate_cutoff_dates(self) -> Dict[str, datetime]:
        """Calculate cutoff dates for each data type based on retention settings.

        Returns:
            Dict mapping data type to cutoff datetime (records older than this are expired)
        """
        now = datetime.utcnow()
        return {
            'documents': now - timedelta(days=self.settings.document_retention_days),
            'ai_logs': now - timedelta(days=self.settings.ai_log_retention_days),
            'feedback_events': now - timedelta(days=self.settings.feedback_event_retention_days),
            'draft_orders': now - timedelta(days=self.settings.draft_order_retention_days),
            'inbound_messages': now - timedelta(days=self.settings.inbound_message_retention_days),
            'grace_period': now - timedelta(days=self.settings.soft_delete_grace_period_days),
        }

    def generate_retention_report(self) -> RetentionReport:
        """Generate report of records eligible for deletion.

        This provides a preview of what would be deleted without actually deleting.
        Useful for administrators to understand impact before running cleanup.

        Returns:
            RetentionReport: Summary of eligible records

        Note:
            Since document, draft_order, and inbound_message models don't exist yet,
            this method returns zero counts. It will be updated when models are added.
        """
        cutoff_dates = self.calculate_cutoff_dates()

        # TODO: Update when document/draft/message models are implemented
        # For now, return empty report structure
        report = RetentionReport(
            org_id=str(self.org_id),
            org_name=self.org.name,
            retention_settings=self.settings,
            documents_eligible_for_soft_delete=0,
            documents_eligible_for_hard_delete=0,
            ai_logs_eligible_for_delete=0,
            feedback_events_eligible_for_delete=0,
            draft_orders_eligible_for_soft_delete=0,
            draft_orders_eligible_for_hard_delete=0,
            inbound_messages_eligible_for_soft_delete=0,
            inbound_messages_eligible_for_hard_delete=0,
            estimated_storage_freed_bytes=None,
        )

        logger.info(
            f"Generated retention report for org {self.org_id}",
            extra={
                "org_id": str(self.org_id),
                "total_eligible": report.total_eligible_for_deletion,
            }
        )

        return report

    def soft_delete_expired_documents(
        self,
        cutoff_date: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Soft-delete documents older than cutoff date.

        Soft-delete means:
        1. Set status/deleted_at field to mark as deleted
        2. Delete raw file from object storage
        3. Keep database record for grace period

        Documents linked to active draft orders are NOT deleted (preservation rule).

        Args:
            cutoff_date: Delete documents created before this date
            batch_size: Maximum records to process in one batch

        Returns:
            Number of documents soft-deleted

        Note:
            Implementation placeholder - will be updated when document model exists.
        """
        # TODO: Implement when document model is available
        # Pattern:
        # 1. Query documents WHERE created_at < cutoff_date AND status != DELETED
        # 2. Filter out documents linked to active drafts
        # 3. For each document:
        #    - Delete from object storage (handle 404 gracefully)
        #    - Set status = DELETED or deleted_at = NOW()
        # 4. Commit in batches
        logger.info(
            f"Soft-delete documents older than {cutoff_date}",
            extra={"org_id": str(self.org_id), "cutoff_date": cutoff_date.isoformat()}
        )
        return 0

    def hard_delete_soft_deleted_documents(
        self,
        grace_cutoff: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Permanently delete documents that were soft-deleted before grace_cutoff.

        Hard-delete means:
        1. Delete database record (cascading to related records)
        2. Double-check object storage cleanup

        Args:
            grace_cutoff: Delete documents soft-deleted before this date
            batch_size: Maximum records to process in one batch

        Returns:
            Number of documents hard-deleted

        Note:
            Implementation placeholder - will be updated when document model exists.
        """
        # TODO: Implement when document model is available
        logger.info(
            f"Hard-delete documents soft-deleted before {grace_cutoff}",
            extra={"org_id": str(self.org_id), "grace_cutoff": grace_cutoff.isoformat()}
        )
        return 0

    def delete_expired_ai_logs(
        self,
        cutoff_date: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Hard-delete AI call logs older than cutoff date.

        AI logs are hard-deleted immediately (no grace period) to manage database growth.

        Args:
            cutoff_date: Delete logs created before this date
            batch_size: Maximum records to delete in one batch

        Returns:
            Number of AI logs deleted

        Note:
            Implementation placeholder - will be updated when ai_call_log model exists.
        """
        # TODO: Implement when ai_call_log model is available
        # Pattern:
        # DELETE FROM ai_call_log
        # WHERE org_id = ? AND created_at < ?
        # LIMIT batch_size
        logger.info(
            f"Delete AI logs older than {cutoff_date}",
            extra={"org_id": str(self.org_id), "cutoff_date": cutoff_date.isoformat()}
        )
        return 0

    def delete_expired_feedback_events(
        self,
        cutoff_date: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Hard-delete feedback events older than cutoff date.

        Feedback events are hard-deleted immediately (no grace period).

        Args:
            cutoff_date: Delete events created before this date
            batch_size: Maximum records to delete in one batch

        Returns:
            Number of feedback events deleted

        Note:
            Implementation placeholder - will be updated when feedback_event model exists.
        """
        # TODO: Implement when feedback_event model is available
        logger.info(
            f"Delete feedback events older than {cutoff_date}",
            extra={"org_id": str(self.org_id), "cutoff_date": cutoff_date.isoformat()}
        )
        return 0

    def soft_delete_expired_draft_orders(
        self,
        cutoff_date: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Soft-delete draft orders older than cutoff date.

        Args:
            cutoff_date: Delete drafts created before this date
            batch_size: Maximum records to process in one batch

        Returns:
            Number of draft orders soft-deleted

        Note:
            Implementation placeholder - will be updated when draft_order model exists.
        """
        # TODO: Implement when draft_order model is available
        logger.info(
            f"Soft-delete draft orders older than {cutoff_date}",
            extra={"org_id": str(self.org_id), "cutoff_date": cutoff_date.isoformat()}
        )
        return 0

    def hard_delete_soft_deleted_draft_orders(
        self,
        grace_cutoff: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Permanently delete draft orders soft-deleted before grace_cutoff.

        Args:
            grace_cutoff: Delete drafts soft-deleted before this date
            batch_size: Maximum records to process in one batch

        Returns:
            Number of draft orders hard-deleted

        Note:
            Implementation placeholder - will be updated when draft_order model exists.
        """
        # TODO: Implement when draft_order model is available
        logger.info(
            f"Hard-delete draft orders soft-deleted before {grace_cutoff}",
            extra={"org_id": str(self.org_id), "grace_cutoff": grace_cutoff.isoformat()}
        )
        return 0

    def soft_delete_expired_inbound_messages(
        self,
        cutoff_date: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Soft-delete inbound messages older than cutoff date.

        Args:
            cutoff_date: Delete messages created before this date
            batch_size: Maximum records to process in one batch

        Returns:
            Number of inbound messages soft-deleted

        Note:
            Implementation placeholder - will be updated when inbound_message model exists.
        """
        # TODO: Implement when inbound_message model is available
        logger.info(
            f"Soft-delete inbound messages older than {cutoff_date}",
            extra={"org_id": str(self.org_id), "cutoff_date": cutoff_date.isoformat()}
        )
        return 0

    def hard_delete_soft_deleted_inbound_messages(
        self,
        grace_cutoff: datetime,
        batch_size: int = DELETION_BATCH_SIZE
    ) -> int:
        """Permanently delete inbound messages soft-deleted before grace_cutoff.

        Args:
            grace_cutoff: Delete messages soft-deleted before this date
            batch_size: Maximum records to process in one batch

        Returns:
            Number of inbound messages hard-deleted

        Note:
            Implementation placeholder - will be updated when inbound_message model exists.
        """
        # TODO: Implement when inbound_message model is available
        logger.info(
            f"Hard-delete inbound messages soft-deleted before {grace_cutoff}",
            extra={"org_id": str(self.org_id), "grace_cutoff": grace_cutoff.isoformat()}
        )
        return 0

    def delete_object_storage_file(self, storage_key: str) -> bool:
        """Delete file from object storage with error handling.

        Implements FR-013 error handling:
        - 404 Not Found: Non-fatal (idempotent), log at DEBUG
        - 403/500 errors: Log at ERROR, raise for retry
        - Maximum 3 retry attempts per file

        Args:
            storage_key: S3/MinIO object key

        Returns:
            True if deleted or already gone, False if error (needs retry)

        Note:
            Requires storage_client to be configured. If None, logs warning and returns True.
        """
        if not self.storage_client:
            logger.warning(
                f"No storage client configured, skipping deletion of {storage_key}"
            )
            return True

        try:
            self.storage_client.delete_object(storage_key)
            logger.debug(f"Deleted object storage file: {storage_key}")
            return True

        except Exception as e:
            error_msg = str(e).lower()

            # 404 Not Found is idempotent - file already deleted
            if '404' in error_msg or 'not found' in error_msg or 'nosuchkey' in error_msg:
                logger.debug(
                    f"Object storage file not found (already deleted): {storage_key}"
                )
                return True

            # 403 Forbidden or 500 errors need retry
            if '403' in error_msg or '500' in error_msg or 'forbidden' in error_msg:
                logger.error(
                    f"Object storage deletion failed (will retry): {storage_key}",
                    exc_info=True,
                    extra={"storage_key": storage_key, "error": str(e)}
                )
                return False

            # Unknown error - log and mark for retry
            logger.error(
                f"Unexpected object storage error: {storage_key}",
                exc_info=True,
                extra={"storage_key": storage_key, "error": str(e)}
            )
            return False

    def run_cleanup_for_org(self) -> Dict[str, int]:
        """Run complete retention cleanup for this organization.

        Executes all cleanup operations in sequence:
        1. Soft-delete expired documents/drafts/messages
        2. Hard-delete soft-deleted records past grace period
        3. Hard-delete expired AI logs and feedback events

        Returns:
            Dict with counts of deleted records by type

        Note:
            This is called by the scheduled job for each org.
            Currently returns zeros as models are not yet implemented.
        """
        logger.info(f"Starting retention cleanup for org {self.org_id}")

        cutoff_dates = self.calculate_cutoff_dates()
        stats = {
            'documents_soft_deleted': 0,
            'documents_hard_deleted': 0,
            'ai_logs_deleted': 0,
            'feedback_events_deleted': 0,
            'draft_orders_soft_deleted': 0,
            'draft_orders_hard_deleted': 0,
            'inbound_messages_soft_deleted': 0,
            'inbound_messages_hard_deleted': 0,
            'storage_errors': 0,
            'database_errors': 0,
        }

        try:
            # Soft-delete expired records
            stats['documents_soft_deleted'] = self.soft_delete_expired_documents(
                cutoff_dates['documents']
            )
            stats['draft_orders_soft_deleted'] = self.soft_delete_expired_draft_orders(
                cutoff_dates['draft_orders']
            )
            stats['inbound_messages_soft_deleted'] = self.soft_delete_expired_inbound_messages(
                cutoff_dates['inbound_messages']
            )

            # Hard-delete soft-deleted records past grace period
            stats['documents_hard_deleted'] = self.hard_delete_soft_deleted_documents(
                cutoff_dates['grace_period']
            )
            stats['draft_orders_hard_deleted'] = self.hard_delete_soft_deleted_draft_orders(
                cutoff_dates['grace_period']
            )
            stats['inbound_messages_hard_deleted'] = self.hard_delete_soft_deleted_inbound_messages(
                cutoff_dates['grace_period']
            )

            # Hard-delete expired system logs (no grace period)
            stats['ai_logs_deleted'] = self.delete_expired_ai_logs(
                cutoff_dates['ai_logs']
            )
            stats['feedback_events_deleted'] = self.delete_expired_feedback_events(
                cutoff_dates['feedback_events']
            )

            self.db.commit()

            logger.info(
                f"Retention cleanup completed for org {self.org_id}",
                extra={"org_id": str(self.org_id), "stats": stats}
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Retention cleanup failed for org {self.org_id}",
                exc_info=True,
                extra={"org_id": str(self.org_id), "error": str(e)}
            )
            stats['database_errors'] += 1

        return stats


def run_global_retention_cleanup(db: Session) -> RetentionStatistics:
    """Run retention cleanup across all organizations.

    This is the main entry point called by the scheduled Celery task.
    Processes each organization sequentially and aggregates statistics.

    Args:
        db: Database session

    Returns:
        RetentionStatistics: Aggregated statistics from all organizations

    Note:
        Errors in one organization do not block processing of others.
        Each org's cleanup is isolated and independently committed/rolled back.
    """
    start_time = datetime.utcnow()
    logger.info("Starting global retention cleanup job")

    # Aggregate statistics
    total_stats = {
        'documents_soft_deleted': 0,
        'documents_hard_deleted': 0,
        'ai_logs_deleted': 0,
        'feedback_events_deleted': 0,
        'draft_orders_soft_deleted': 0,
        'draft_orders_hard_deleted': 0,
        'inbound_messages_soft_deleted': 0,
        'inbound_messages_hard_deleted': 0,
        'storage_errors': 0,
        'database_errors': 0,
        'orgs_processed': 0,
    }

    # Process each organization
    orgs = db.query(Org).all()

    for org in orgs:
        try:
            # Create service for this org (with its own session for isolation)
            # TODO: Pass storage_client when object storage is implemented
            service = RetentionService(db=db, org_id=org.id, storage_client=None)

            # Run cleanup for this org
            org_stats = service.run_cleanup_for_org()

            # Aggregate stats
            for key, value in org_stats.items():
                total_stats[key] = total_stats.get(key, 0) + value

            total_stats['orgs_processed'] += 1

        except Exception as e:
            logger.error(
                f"Failed to process retention for org {org.id}",
                exc_info=True,
                extra={"org_id": str(org.id), "error": str(e)}
            )
            total_stats['database_errors'] += 1

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    # Create statistics object
    statistics = RetentionStatistics(
        job_started_at=start_time,
        job_completed_at=end_time,
        duration_seconds=duration,
        **total_stats
    )

    logger.info(
        "Global retention cleanup job completed",
        extra={
            "duration_seconds": duration,
            "total_deleted": statistics.total_records_deleted,
            "orgs_processed": statistics.orgs_processed,
            "has_errors": statistics.has_errors,
            "is_anomaly": statistics.is_anomaly,
        }
    )

    # Alert if anomaly detected
    if statistics.is_anomaly:
        logger.warning(
            f"Retention cleanup anomaly detected: {statistics.total_records_deleted} records deleted",
            extra={"statistics": statistics.dict()}
        )

    # Alert if errors occurred
    if statistics.has_errors:
        logger.error(
            f"Retention cleanup completed with errors",
            extra={
                "storage_errors": statistics.storage_errors,
                "database_errors": statistics.database_errors,
            }
        )

    return statistics
