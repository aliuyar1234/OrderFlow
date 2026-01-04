"""Attachment Extraction Worker for SMTP-received emails.

Background worker that extracts attachments from inbound messages,
stores them to object storage, and creates document records.

SSOT Reference: spec 006-smtp-ingest, §3.3 (SMTP Ingest)
Architecture: Celery worker following multi-tenant isolation patterns
"""

import logging
from typing import Dict, Any
from uuid import UUID
from io import BytesIO

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..models.inbound_message import (
    InboundMessage,
    InboundMessageStatus,
)
from ..models.document import Document, DocumentStatus
from ..infrastructure.ingest.mime_parser import (
    parse_mime_message,
    extract_attachments,
)
from .base import validate_org_id, get_scoped_session

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def extract_attachments_task(
    self,
    inbound_message_id: str,
    org_id: str,
) -> Dict[str, Any]:
    """Extract attachments from inbound message and create document records.

    This task is enqueued after an email is received via SMTP. It:
    1. Retrieves the inbound_message record
    2. Downloads raw MIME from object storage
    3. Parses MIME and extracts all attachments
    4. Stores each attachment to object storage
    5. Creates document record for each attachment
    6. Updates inbound_message status to PARSED

    Task Signature Pattern (§11.2):
    - Takes explicit org_id for tenant isolation
    - Validates org exists before processing
    - Uses scoped session with org context
    - All queries filtered by org_id

    Args:
        inbound_message_id: UUID string of inbound_message to process
        org_id: UUID string of organization (tenant isolation)

    Returns:
        Dict with processing results:
            {
                "status": "success",
                "inbound_message_id": str,
                "documents_created": int,
                "attachment_count": int
            }

    Raises:
        ValueError: If org_id invalid or inbound_message not found
        Exception: If attachment extraction fails (retried up to 3 times)
    """
    # Validate org_id and get scoped session
    org_uuid = validate_org_id(org_id)
    session = get_scoped_session(org_uuid)

    try:
        # Load inbound message with org_id filter
        inbound_message_uuid = UUID(inbound_message_id)
        stmt = select(InboundMessage).where(
            InboundMessage.id == inbound_message_uuid,
            InboundMessage.org_id == org_uuid
        )
        result = session.execute(stmt)
        inbound_msg = result.scalar_one_or_none()

        if not inbound_msg:
            raise ValueError(
                f"InboundMessage {inbound_message_id} not found "
                f"in org {org_id}"
            )

        logger.info(
            f"Processing inbound_message {inbound_msg.id} for org {org_id}"
        )

        # Update status to STORED
        inbound_msg.status = InboundMessageStatus.STORED.value
        session.commit()

        # Get storage adapter (injected via settings)
        from ..infrastructure.storage.s3_storage_adapter import get_storage_adapter
        storage_adapter = get_storage_adapter()

        # Retrieve raw MIME from storage
        if not inbound_msg.raw_storage_key:
            raise ValueError(
                f"InboundMessage {inbound_msg.id} has no raw_storage_key"
            )

        try:
            raw_mime_file = storage_adapter.retrieve_file(
                inbound_msg.raw_storage_key
            )
            raw_mime = raw_mime_file.read()
        except Exception as e:
            logger.error(f"Failed to retrieve raw MIME: {e}")
            inbound_msg.status = InboundMessageStatus.FAILED.value
            inbound_msg.error_json = {
                "error": "storage_retrieval_failed",
                "message": str(e)
            }
            session.commit()
            raise

        # Parse MIME message
        try:
            msg = parse_mime_message(raw_mime)
            attachments = extract_attachments(msg)
        except Exception as e:
            logger.error(f"Failed to parse MIME: {e}")
            inbound_msg.status = InboundMessageStatus.FAILED.value
            inbound_msg.error_json = {
                "error": "mime_parsing_failed",
                "message": str(e)
            }
            session.commit()
            raise

        logger.info(f"Extracted {len(attachments)} attachments from message")

        # No attachments - log warning but mark as parsed
        if len(attachments) == 0:
            logger.warning(
                f"InboundMessage {inbound_msg.id} has no attachments"
            )
            inbound_msg.status = InboundMessageStatus.PARSED.value
            session.commit()
            return {
                "status": "success",
                "inbound_message_id": str(inbound_msg.id),
                "documents_created": 0,
                "attachment_count": 0,
                "warning": "no_attachments"
            }

        # Process each attachment
        document_ids = []
        for attachment in attachments:
            try:
                # Store attachment to object storage
                stored_file = storage_adapter.store_file(
                    file=attachment.as_file(),
                    org_id=org_uuid,
                    filename=attachment.filename,
                    mime_type=attachment.mime_type,
                )

                # Create document record
                document = Document(
                    org_id=org_uuid,
                    inbound_message_id=inbound_msg.id,
                    file_name=attachment.filename,
                    mime_type=attachment.mime_type,
                    size_bytes=attachment.size_bytes,
                    sha256=stored_file.sha256,
                    storage_key=stored_file.storage_key,
                    status=DocumentStatus.STORED.value,
                )

                session.add(document)
                session.flush()  # Get document.id
                document_ids.append(str(document.id))

                logger.info(
                    f"Created document {document.id} for attachment "
                    f"{attachment.filename} ({attachment.size_bytes} bytes)"
                )

            except Exception as e:
                logger.error(
                    f"Failed to process attachment {attachment.filename}: {e}"
                )
                # Continue processing other attachments
                continue

        # Update status to PARSED
        inbound_msg.status = InboundMessageStatus.PARSED.value
        session.commit()

        logger.info(
            f"Successfully processed inbound_message {inbound_msg.id}: "
            f"{len(document_ids)} documents created from {len(attachments)} attachments"
        )

        return {
            "status": "success",
            "inbound_message_id": str(inbound_msg.id),
            "documents_created": len(document_ids),
            "attachment_count": len(attachments),
            "document_ids": document_ids,
        }

    except Exception as e:
        session.rollback()
        logger.error(
            f"Attachment extraction failed for message {inbound_message_id}: {e}",
            exc_info=True
        )

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    finally:
        session.close()


async def enqueue_attachment_extraction(
    inbound_message_id: str,
    org_id: str,
) -> None:
    """Enqueue attachment extraction task (async wrapper).

    Args:
        inbound_message_id: UUID string of inbound_message
        org_id: UUID string of organization
    """
    extract_attachments_task.delay(
        inbound_message_id=inbound_message_id,
        org_id=org_id,
    )
    logger.info(
        f"Enqueued attachment extraction: message={inbound_message_id}, org={org_id}"
    )
