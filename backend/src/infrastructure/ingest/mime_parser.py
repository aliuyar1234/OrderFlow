"""MIME Parser for email attachment extraction.

Handles parsing of MIME messages, extraction of metadata, and attachment processing.
Supports RFC 2047 encoded filenames and nested multipart messages.

SSOT Reference: §3.3 (SMTP Ingest), spec 006-smtp-ingest
"""

import email
import email.policy
import hashlib
import logging
from email.message import Message
from typing import List, Optional, Tuple, BinaryIO
from io import BytesIO

logger = logging.getLogger(__name__)


class AttachmentInfo:
    """Information about an email attachment."""
    
    def __init__(
        self,
        filename: str,
        content: bytes,
        mime_type: str,
        size_bytes: int
    ):
        self.filename = filename
        self.content = content
        self.mime_type = mime_type
        self.size_bytes = size_bytes
    
    def as_file(self) -> BinaryIO:
        """Return attachment content as file-like object."""
        return BytesIO(self.content)


class EmailMetadata:
    """Extracted metadata from email message."""
    
    def __init__(
        self,
        message_id: Optional[str],
        from_email: Optional[str],
        to_email: Optional[str],
        subject: Optional[str],
        date: Optional[str],
    ):
        self.message_id = message_id
        self.from_email = from_email
        self.to_email = to_email
        self.subject = subject
        self.date = date


def parse_mime_message(raw_mime: bytes) -> Message:
    """Parse raw MIME bytes into email.Message object.
    
    Args:
        raw_mime: Raw MIME message bytes
        
    Returns:
        email.Message: Parsed MIME message
        
    Raises:
        ValueError: If MIME parsing fails
    """
    try:
        msg = email.message_from_bytes(
            raw_mime,
            policy=email.policy.default
        )
        return msg
    except Exception as e:
        logger.error(f"Failed to parse MIME message: {e}")
        raise ValueError(f"Invalid MIME message: {e}")


def extract_metadata(msg: Message) -> EmailMetadata:
    """Extract email metadata from parsed MIME message.
    
    Args:
        msg: Parsed email message
        
    Returns:
        EmailMetadata: Extracted metadata
    """
    # Extract Message-ID (or generate synthetic if missing)
    message_id = msg.get('Message-ID')
    if not message_id:
        # Generate synthetic Message-ID from hash of headers
        header_hash = hashlib.sha256(
            f"{msg.get('From', '')}{msg.get('To', '')}"
            f"{msg.get('Subject', '')}{msg.get('Date', '')}".encode()
        ).hexdigest()[:16]
        message_id = f"<synthetic-{header_hash}@orderflow.generated>"
        logger.warning(
            f"Email missing Message-ID, generated synthetic: {message_id}"
        )
    
    return EmailMetadata(
        message_id=message_id,
        from_email=msg.get('From'),
        to_email=msg.get('To'),
        subject=msg.get('Subject'),
        date=msg.get('Date'),
    )


def extract_attachments(msg: Message) -> List[AttachmentInfo]:
    """Extract all file attachments from MIME message.
    
    Walks the entire MIME tree to find attachments. Skips:
    - Multipart containers
    - Parts without Content-Disposition
    - Inline images (Content-Disposition: inline)
    - Parts without filename
    
    Args:
        msg: Parsed email message
        
    Returns:
        List[AttachmentInfo]: List of extracted attachments
    """
    attachments = []
    
    for part in msg.walk():
        # Skip multipart containers
        if part.get_content_maintype() == 'multipart':
            continue
        
        # Check if this is an attachment
        content_disposition = part.get('Content-Disposition')
        if not content_disposition:
            continue
        
        # Skip inline content (images, signatures)
        if 'inline' in content_disposition.lower():
            continue
        
        # Get filename (handles RFC 2047 encoding)
        filename = part.get_filename()
        if not filename:
            continue
        
        # Extract content
        try:
            content = part.get_payload(decode=True)
            if not content:
                logger.warning(f"Attachment {filename} has no content, skipping")
                continue
            
            mime_type = part.get_content_type()
            size_bytes = len(content)
            
            attachments.append(AttachmentInfo(
                filename=filename,
                content=content,
                mime_type=mime_type,
                size_bytes=size_bytes
            ))
            
            logger.info(
                f"Extracted attachment: {filename} ({mime_type}, {size_bytes} bytes)"
            )
            
        except Exception as e:
            logger.error(f"Failed to extract attachment {filename}: {e}")
            continue
    
    return attachments


def generate_synthetic_message_id(from_email: str, to_email: str, subject: str, date: str) -> str:
    """Generate synthetic Message-ID for emails missing the header.
    
    Creates a deterministic Message-ID based on email metadata. This ensures
    consistent deduplication even if the same email is received multiple times.
    
    Args:
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject
        date: Email date header
        
    Returns:
        str: Synthetic Message-ID in RFC 5322 format
    """
    header_data = f"{from_email}{to_email}{subject}{date}".encode()
    header_hash = hashlib.sha256(header_data).hexdigest()[:16]
    return f"<synthetic-{header_hash}@orderflow.generated>"
