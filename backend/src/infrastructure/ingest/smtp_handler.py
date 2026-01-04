"""SMTP Handler for OrderFlow email ingestion.

Implements aiosmtpd handler for receiving order emails with plus-addressing
for multi-tenant routing. Stores raw MIME to object storage and enqueues
attachment extraction jobs.

SSOT Reference: §3.3-3.4 (SMTP Ingest), spec 006-smtp-ingest
Architecture: Hexagonal - Infrastructure adapter implementing email ingestion
"""

import asyncio
import logging
import re
from typing import Optional
from uuid import UUID

from aiosmtpd.smtp import Envelope, Session, SMTP
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.inbound_message import (
    InboundMessage,
    InboundMessageSource,
    InboundMessageStatus,
)
from ...models.org import Org
from .mime_parser import parse_mime_message, extract_metadata

logger = logging.getLogger(__name__)


class OrderFlowSMTPHandler:
    """SMTP handler for OrderFlow email ingestion.

    Handles incoming emails with plus-addressing for org routing:
    - orders+acme@orderflow.example.com → routes to org with slug 'acme'
    - orders@orderflow.example.com → rejects (no default org)

    Email processing:
    1. Extract org_slug from recipient (plus-addressing)
    2. Validate org exists
    3. Parse MIME message and extract metadata
    4. Store raw MIME to object storage
    5. Create inbound_message record
    6. Enqueue attachment extraction job

    Deduplication:
    - Same Message-ID for same org is rejected (database unique constraint)
    - Returns SMTP 250 (success) to avoid sender retries
    - Logs warning for duplicate detection
    """

    def __init__(
        self,
        get_db_session,
        storage_adapter,
        enqueue_extraction_job,
    ):
        """Initialize SMTP handler.

        Args:
            get_db_session: Async context manager returning AsyncSession
            storage_adapter: Object storage adapter (ObjectStoragePort)
            enqueue_extraction_job: Callable to enqueue extraction job
        """
        self.get_db_session = get_db_session
        self.storage_adapter = storage_adapter
        self.enqueue_extraction_job = enqueue_extraction_job

    def extract_org_slug(self, email_address: str) -> Optional[str]:
        """Extract org slug from plus-addressed email.

        Examples:
            orders+acme@orderflow.example.com → 'acme'
            orders+test-org@orderflow.example.com → 'test-org'
            orders@orderflow.example.com → None

        Args:
            email_address: Email address to parse

        Returns:
            Optional[str]: Org slug or None if no plus-addressing
        """
        match = re.match(r'^[^+]+\+([^@]+)@', email_address)
        if match:
            return match.group(1)
        return None

    async def get_org_by_slug(
        self,
        session: AsyncSession,
        slug: str
    ) -> Optional[Org]:
        """Retrieve org by slug.

        Args:
            session: Database session
            slug: Organization slug

        Returns:
            Optional[Org]: Org instance or None if not found
        """
        stmt = select(Org).where(Org.slug == slug)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def store_raw_mime(
        self,
        raw_mime: bytes,
        org_id: UUID,
        message_id: str,
    ) -> str:
        """Store raw MIME message to object storage.

        Args:
            raw_mime: Raw MIME message bytes
            org_id: Organization UUID
            message_id: Email Message-ID

        Returns:
            str: Storage key for retrieving the raw MIME

        Raises:
            Exception: If storage operation fails
        """
        from io import BytesIO

        # Generate filename from message_id
        safe_message_id = re.sub(r'[^a-zA-Z0-9-]', '_', message_id)
        filename = f"raw_mime_{safe_message_id}.eml"

        # Store to S3
        stored_file = await self.storage_adapter.store_file(
            file=BytesIO(raw_mime),
            org_id=org_id,
            filename=filename,
            mime_type='message/rfc822',
        )

        return stored_file.storage_key

    async def handle_DATA(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
    ) -> str:
        """Handle email DATA command (main SMTP handler entry point).

        Called by aiosmtpd when email content is received. This is the main
        entry point for email processing.

        Args:
            server: SMTP server instance
            session: SMTP session
            envelope: Email envelope (content, sender, recipients)

        Returns:
            str: SMTP response code and message
                '250 Message accepted' - Success
                '550 Unknown recipient' - Invalid org slug
                '451 Temporary error' - Processing failure
        """
        try:
            # Get recipient (first rcpt_to)
            if not envelope.rcpt_tos:
                logger.warning("Email received with no recipients")
                return '550 No valid recipients'

            to_email = envelope.rcpt_tos[0]
            from_email = envelope.mail_from

            logger.info(
                f"Received email: from={from_email}, to={to_email}, "
                f"size={len(envelope.content)} bytes"
            )

            # Extract org slug from plus-addressing
            org_slug = self.extract_org_slug(to_email)
            if not org_slug:
                logger.warning(
                    f"Email to {to_email} missing plus-addressing, rejecting"
                )
                return '550 Unknown recipient organization'

            # Parse MIME message
            try:
                msg = parse_mime_message(envelope.content)
                metadata = extract_metadata(msg)
            except Exception as e:
                logger.error(f"Failed to parse MIME message: {e}")
                return '451 Message parsing failed'

            # Validate org exists
            async with self.get_db_session() as session:
                org = await self.get_org_by_slug(session, org_slug)
                if not org:
                    logger.warning(
                        f"Email for unknown org slug: {org_slug}, rejecting"
                    )
                    return '550 Unknown recipient organization'

                # Store raw MIME to object storage
                try:
                    raw_storage_key = await self.store_raw_mime(
                        envelope.content,
                        org.id,
                        metadata.message_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to store raw MIME: {e}")
                    return '451 Storage error'

                # Create inbound_message record
                try:
                    inbound_msg = InboundMessage(
                        org_id=org.id,
                        source=InboundMessageSource.EMAIL.value,
                        source_message_id=metadata.message_id,
                        from_email=from_email,
                        to_email=to_email,
                        subject=metadata.subject,
                        raw_storage_key=raw_storage_key,
                        status=InboundMessageStatus.RECEIVED.value,
                    )

                    session.add(inbound_msg)
                    await session.commit()
                    await session.refresh(inbound_msg)

                    logger.info(
                        f"Created inbound_message: id={inbound_msg.id}, "
                        f"org={org.slug}, message_id={metadata.message_id}"
                    )

                except IntegrityError as e:
                    # Duplicate message_id for this org
                    await session.rollback()

                    if 'idx_inbound_unique_source_message' in str(e):
                        logger.warning(
                            f"Duplicate email detected: message_id={metadata.message_id}, "
                            f"org={org.slug}. Skipping (idempotent)."
                        )
                        # Return success to avoid sender retries
                        return '250 Message accepted (duplicate)'

                    # Other integrity error
                    logger.error(f"Database integrity error: {e}")
                    return '451 Database error'

                # Enqueue attachment extraction job
                try:
                    await self.enqueue_extraction_job(
                        inbound_message_id=str(inbound_msg.id),
                        org_id=str(org.id),
                    )
                    logger.info(
                        f"Enqueued attachment extraction for message {inbound_msg.id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to enqueue extraction job: {e}. "
                        f"Message stored but requires manual processing."
                    )
                    # Do not fail email receipt if queueing fails
                    # Message is safely stored and can be processed manually

            return '250 Message accepted'

        except Exception as e:
            logger.error(f"Unexpected error processing email: {e}", exc_info=True)
            return '451 Temporary server error'
