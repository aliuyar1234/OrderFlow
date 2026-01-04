"""Extraction worker - Celery task for extracting data from documents.

Handles background extraction of order data from uploaded documents (Excel, CSV, PDF).
Updates document status and creates extraction_run records.

SSOT Reference: §7 (Extraction Logic), §11.2 (Multi-Tenant Background Jobs)
"""

import logging
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from celery import shared_task
from sqlalchemy.orm import Session

from .base import BaseTask, validate_org_id, get_scoped_session
from ..models import Document, DocumentStatus, ExtractionRun, ExtractionRunStatus
from ..infrastructure.extractors import get_global_registry

logger = logging.getLogger(__name__)


@shared_task(name="extraction.extract_document", base=BaseTask, bind=True, max_retries=3)
def extract_document_task(
    self,
    document_id: str,
    org_id: str,
) -> Dict[str, Any]:
    """Extract structured order data from document (background task).

    This task:
    1. Loads document from database
    2. Updates document status to PROCESSING
    3. Creates extraction_run record with status=RUNNING
    4. Selects appropriate extractor based on MIME type
    5. Executes extraction
    6. Stores output_json in extraction_run
    7. Updates document status to EXTRACTED or FAILED
    8. Returns result summary

    Args:
        document_id: UUID string of document to extract
        org_id: UUID string of organization (REQUIRED for tenant isolation)

    Returns:
        Dict with extraction result:
        - status: 'success' or 'failed'
        - document_id: Document UUID
        - extraction_run_id: ExtractionRun UUID
        - confidence: Confidence score (if success)
        - lines_extracted: Number of lines extracted (if success)
        - error: Error message (if failed)

    Raises:
        ValueError: If org_id invalid or document not found
        Exception: Other errors trigger retry with exponential backoff

    Example:
        # Enqueue from API endpoint
        extract_document_task.delay(
            document_id=str(document.id),
            org_id=str(current_user.org_id)
        )
    """
    # Validate org_id (automatic via BaseTask, but explicit is clearer)
    org_uuid = validate_org_id(org_id)
    doc_uuid = UUID(document_id)

    # Get scoped session
    session = get_scoped_session(org_uuid)

    try:
        # Load document with explicit org_id filter
        document = session.query(Document).filter(
            Document.id == doc_uuid,
            Document.org_id == org_uuid
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found in org {org_id}")

        logger.info(
            f"Starting extraction for document {document_id} "
            f"(mime_type={document.mime_type}, org={org_id})"
        )

        # Update document status to PROCESSING
        document.status = DocumentStatus.PROCESSING
        session.commit()

        # Create extraction_run record
        extraction_run = ExtractionRun(
            org_id=org_uuid,
            document_id=doc_uuid,
            status=ExtractionRunStatus.RUNNING,
            started_at=datetime.utcnow(),
            extractor_version="",  # Will be set by extractor
        )
        session.add(extraction_run)
        session.commit()

        extraction_run_id = extraction_run.id
        logger.info(f"Created extraction_run {extraction_run_id}")

        # Get extractor registry
        registry = get_global_registry()

        # Select extractor based on MIME type
        extractor = registry.get_extractor(document.mime_type)

        if not extractor:
            error_msg = f"No extractor available for MIME type: {document.mime_type}"
            logger.error(error_msg)

            # Update extraction_run to FAILED
            extraction_run.status = ExtractionRunStatus.FAILED
            extraction_run.finished_at = datetime.utcnow()
            extraction_run.error_json = {"error": error_msg, "mime_type": document.mime_type}

            # Update document to FAILED
            document.status = DocumentStatus.FAILED
            document.error_json = {"error": error_msg}

            session.commit()

            return {
                "status": "failed",
                "document_id": document_id,
                "extraction_run_id": str(extraction_run_id),
                "error": error_msg,
            }

        # Update extractor_version
        extraction_run.extractor_version = extractor.version
        session.commit()

        logger.info(f"Using extractor: {extractor.version} (priority={extractor.priority})")

        # Execute extraction (async function - need to handle properly)
        # For now, we'll need to make the task async or use asyncio.run
        # Since Celery tasks are sync by default, we'll use asyncio.run
        import asyncio
        result = asyncio.run(extractor.extract(document))

        if result.success:
            # Store output and metrics
            extraction_run.output_json = result.output.dict() if result.output else None
            extraction_run.status = ExtractionRunStatus.SUCCEEDED
            extraction_run.finished_at = datetime.utcnow()
            extraction_run.metrics_json = result.metrics

            # Update document status to EXTRACTED
            document.status = DocumentStatus.EXTRACTED

            session.commit()

            logger.info(
                f"Extraction succeeded: document={document_id}, "
                f"extraction_run={extraction_run_id}, "
                f"confidence={result.confidence:.3f}, "
                f"lines={len(result.output.lines) if result.output else 0}"
            )

            return {
                "status": "success",
                "document_id": document_id,
                "extraction_run_id": str(extraction_run_id),
                "confidence": result.confidence,
                "lines_extracted": len(result.output.lines) if result.output else 0,
                "runtime_ms": result.metrics.get('runtime_ms', 0),
            }

        else:
            # Extraction failed
            extraction_run.status = ExtractionRunStatus.FAILED
            extraction_run.finished_at = datetime.utcnow()
            extraction_run.error_json = {
                "error": result.error,
                "extractor_version": extractor.version,
            }
            extraction_run.metrics_json = result.metrics

            # Update document status to FAILED
            document.status = DocumentStatus.FAILED
            document.error_json = {"extraction_error": result.error}

            session.commit()

            logger.warning(
                f"Extraction failed: document={document_id}, "
                f"extraction_run={extraction_run_id}, "
                f"error={result.error}"
            )

            return {
                "status": "failed",
                "document_id": document_id,
                "extraction_run_id": str(extraction_run_id),
                "error": result.error,
            }

    except Exception as e:
        # Unexpected error - rollback and retry
        session.rollback()

        logger.error(
            f"Extraction task failed with exception: document={document_id}, error={e}",
            exc_info=True
        )

        # Update extraction_run if it exists
        try:
            if 'extraction_run_id' in locals():
                extraction_run = session.query(ExtractionRun).filter(
                    ExtractionRun.id == extraction_run_id
                ).first()

                if extraction_run:
                    extraction_run.status = ExtractionRunStatus.FAILED
                    extraction_run.finished_at = datetime.utcnow()
                    extraction_run.error_json = {
                        "exception": str(e),
                        "type": type(e).__name__,
                    }

            # Update document status
            document = session.query(Document).filter(
                Document.id == doc_uuid,
                Document.org_id == org_uuid
            ).first()

            if document:
                document.status = DocumentStatus.FAILED
                document.error_json = {"exception": str(e)}

            session.commit()

        except Exception as commit_error:
            logger.error(f"Failed to update failure status: {commit_error}")

        # Retry with exponential backoff
        retry_countdown = 2 ** self.request.retries * 60  # 1min, 2min, 4min
        raise self.retry(exc=e, countdown=retry_countdown)

    finally:
        session.close()


@shared_task(name="extraction.retry_failed_extractions", bind=True)
def retry_failed_extractions_task(self, org_id: str, max_retries: int = 10) -> Dict[str, Any]:
    """Retry extraction for failed documents.

    Finds documents with status=FAILED and re-enqueues extraction tasks.
    Useful for batch retry after fixing extractor bugs or infrastructure issues.

    Args:
        org_id: UUID string of organization
        max_retries: Maximum number of documents to retry (default 10)

    Returns:
        Dict with retry statistics:
        - retried_count: Number of documents re-enqueued
        - document_ids: List of document IDs retried

    Note:
        This task is typically triggered manually or via scheduled job,
        not automatically after failures.
    """
    org_uuid = validate_org_id(org_id)
    session = get_scoped_session(org_uuid)

    try:
        # Find failed documents (limit to max_retries)
        failed_docs = session.query(Document).filter(
            Document.org_id == org_uuid,
            Document.status == DocumentStatus.FAILED
        ).limit(max_retries).all()

        logger.info(f"Found {len(failed_docs)} failed documents to retry for org {org_id}")

        retried_ids = []
        for doc in failed_docs:
            # Enqueue extraction task
            extract_document_task.delay(
                document_id=str(doc.id),
                org_id=org_id
            )
            retried_ids.append(str(doc.id))

        logger.info(f"Re-enqueued {len(retried_ids)} extraction tasks for org {org_id}")

        return {
            "status": "success",
            "retried_count": len(retried_ids),
            "document_ids": retried_ids,
        }

    finally:
        session.close()
