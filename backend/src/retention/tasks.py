"""Celery tasks for data retention cleanup.

This module defines scheduled tasks for automatic retention cleanup.

Tasks:
- retention_cleanup_task: Daily job running at 02:00 UTC

SSOT Reference: §11.5 (Data Retention), FR-001
"""

import logging
from celery import shared_task
from typing import Dict, Any

from ..database import SessionLocal
from .service import run_global_retention_cleanup

logger = logging.getLogger(__name__)


@shared_task(name="retention.cleanup", bind=True)
def retention_cleanup_task(self) -> Dict[str, Any]:
    """Execute global retention cleanup across all organizations.

    This task is scheduled to run daily at 02:00 UTC via Celery Beat.
    It processes all organizations sequentially and logs statistics.

    The task is idempotent - safe to run multiple times without side effects.
    Running twice in succession will find no additional records to delete.

    Returns:
        Dict with cleanup statistics:
        - documents_soft_deleted: Number of documents soft-deleted
        - documents_hard_deleted: Number of documents permanently deleted
        - ai_logs_deleted: Number of AI logs deleted
        - feedback_events_deleted: Number of feedback events deleted
        - draft_orders_soft_deleted: Number of drafts soft-deleted
        - draft_orders_hard_deleted: Number of drafts permanently deleted
        - inbound_messages_soft_deleted: Number of messages soft-deleted
        - inbound_messages_hard_deleted: Number of messages permanently deleted
        - storage_errors: Number of object storage errors
        - database_errors: Number of database errors
        - orgs_processed: Number of organizations processed
        - duration_seconds: Total execution time

    Raises:
        Exception: Logs errors but does not raise (task always completes)

    Example Celery Beat schedule configuration:
        from celery.schedules import crontab

        celery_app.conf.beat_schedule = {
            'retention-cleanup-daily': {
                'task': 'retention.cleanup',
                'schedule': crontab(hour=2, minute=0),  # 02:00 UTC
                'options': {
                    'expires': 3600,  # Task expires after 1 hour if not picked up
                },
            },
        }
    """
    logger.info("Retention cleanup task started")

    db = SessionLocal()
    try:
        # Run global cleanup
        statistics = run_global_retention_cleanup(db)

        # Convert to dict for Celery result
        result = {
            'status': 'completed',
            'job_started_at': statistics.job_started_at.isoformat(),
            'job_completed_at': statistics.job_completed_at.isoformat(),
            'duration_seconds': statistics.duration_seconds,
            'documents_soft_deleted': statistics.documents_soft_deleted,
            'documents_hard_deleted': statistics.documents_hard_deleted,
            'ai_logs_deleted': statistics.ai_logs_deleted,
            'feedback_events_deleted': statistics.feedback_events_deleted,
            'draft_orders_soft_deleted': statistics.draft_orders_soft_deleted,
            'draft_orders_hard_deleted': statistics.draft_orders_hard_deleted,
            'inbound_messages_soft_deleted': statistics.inbound_messages_soft_deleted,
            'inbound_messages_hard_deleted': statistics.inbound_messages_hard_deleted,
            'storage_errors': statistics.storage_errors,
            'database_errors': statistics.database_errors,
            'orgs_processed': statistics.orgs_processed,
            'total_deleted': statistics.total_records_deleted,
            'has_errors': statistics.has_errors,
            'is_anomaly': statistics.is_anomaly,
        }

        logger.info(
            "Retention cleanup task completed successfully",
            extra=result
        )

        return result

    except Exception as e:
        logger.error(
            "Retention cleanup task failed",
            exc_info=True,
            extra={"error": str(e)}
        )

        # Return error status but don't raise (allow task to complete)
        return {
            'status': 'failed',
            'error': str(e),
            'total_deleted': 0,
        }

    finally:
        db.close()


@shared_task(name="retention.cleanup_org", bind=True)
def retention_cleanup_org_task(self, org_id: str) -> Dict[str, Any]:
    """Execute retention cleanup for a specific organization.

    This task allows manual triggering of retention cleanup for a single org.
    Useful for testing or handling special cases.

    Args:
        org_id: Organization UUID as string

    Returns:
        Dict with cleanup statistics for the organization

    Raises:
        ValueError: If org_id is invalid or organization not found
    """
    from uuid import UUID
    from .service import RetentionService

    logger.info(f"Retention cleanup task started for org {org_id}")

    db = SessionLocal()
    try:
        org_uuid = UUID(org_id)

        # Create service for this org
        service = RetentionService(db=db, org_id=org_uuid, storage_client=None)

        # Run cleanup
        stats = service.run_cleanup_for_org()

        result = {
            'status': 'completed',
            'org_id': org_id,
            **stats
        }

        logger.info(
            f"Retention cleanup completed for org {org_id}",
            extra=result
        )

        return result

    except ValueError as e:
        logger.error(
            f"Invalid org_id: {org_id}",
            extra={"error": str(e)}
        )
        raise

    except Exception as e:
        logger.error(
            f"Retention cleanup failed for org {org_id}",
            exc_info=True,
            extra={"org_id": org_id, "error": str(e)}
        )

        return {
            'status': 'failed',
            'org_id': org_id,
            'error': str(e),
        }

    finally:
        db.close()
