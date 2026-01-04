"""Upload API endpoints for OrderFlow

Provides POST /uploads endpoint for manual document upload.
Validates file types, size, calculates SHA256, stores files in object storage,
creates document and inbound_message records, and triggers extraction.

SSOT Reference: §8.5 (Upload API)
Spec: 007-document-upload
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..database import get_db
from ..models.document import Document, DocumentStatus
from ..models.inbound_message import InboundMessage
from ..auth.dependencies import CurrentUser
from ..auth.roles import require_role, Role
from ..domain.documents import (
    is_supported_mime_type,
    validate_file_size,
    validate_filename,
    sanitize_filename,
    MAX_FILE_SIZE,
    MAX_BATCH_FILES,
)
from ..domain.documents.ports.object_storage_port import ObjectStoragePort
from ..infrastructure.storage.s3_storage_adapter import S3StorageAdapter
from ..infrastructure.storage.storage_config import load_storage_config_from_env
from .schemas import (
    UploadResponse,
    UploadedDocumentResponse,
    FailedUploadResponse,
    UploadErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["Uploads"])


def get_storage() -> ObjectStoragePort:
    """Dependency for object storage adapter

    Loads storage config from environment and returns S3 adapter instance.
    """
    config = load_storage_config_from_env()
    return S3StorageAdapter(
        endpoint_url=config.endpoint_url,
        access_key=config.access_key,
        secret_key=config.secret_key,
        bucket_name=config.bucket_name,
        region=config.region,
    )


async def check_duplicate_document(
    db: Session,
    org_id: UUID,
    sha256: str,
    file_name: str,
    size_bytes: int
) -> bool:
    """Check if identical document already exists (deduplication)

    Uses unique index on (org_id, sha256, file_name, size_bytes) to detect duplicates.
    Per SSOT §5.4.6, deduplication is org-scoped only.

    Args:
        db: Database session
        org_id: Organization UUID
        sha256: SHA256 hash (hex format)
        file_name: Original filename
        size_bytes: File size in bytes

    Returns:
        True if duplicate exists, False otherwise
    """
    existing = db.query(Document).filter(
        and_(
            Document.org_id == org_id,
            Document.sha256 == sha256,
            Document.file_name == file_name,
            Document.size_bytes == size_bytes
        )
    ).first()

    return existing is not None


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    files: Annotated[List[UploadFile], File(...)],
    current_user: Annotated[CurrentUser, Depends(require_role([Role.ADMIN, Role.OPS, Role.INTEGRATOR]))],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[ObjectStoragePort, Depends(get_storage)]
):
    """Upload one or more documents for processing

    Accepts multipart/form-data with one or more files. Supported file types:
    - PDF (application/pdf)
    - Excel (.xls, .xlsx)
    - CSV (text/csv)

    Validation:
    - File type (MIME type validation)
    - File size (max 100MB by default, configurable via MAX_UPLOAD_SIZE_BYTES)
    - Filename sanity checks

    Processing:
    1. Validate file type and size
    2. Calculate SHA256 hash during upload
    3. Store file in object storage (with deduplication)
    4. Create inbound_message record with source=UPLOAD
    5. Create document record with status=STORED
    6. Enqueue extraction job (TODO: not yet implemented)

    Multi-tenant isolation: org_id from JWT, all records scoped to user's organization.

    Args:
        files: List of uploaded files (multipart/form-data)
        current_user: Authenticated user (must be ADMIN, OPS, or INTEGRATOR)
        db: Database session
        storage: Object storage adapter

    Returns:
        UploadResponse: Lists of successfully uploaded and failed documents

    Raises:
        HTTPException 400: If batch size exceeds MAX_BATCH_FILES
        HTTPException 403: If user doesn't have required role

    Example:
        curl -X POST https://api.orderflow.com/api/v1/uploads \\
             -H "Authorization: Bearer $TOKEN" \\
             -F "files=@order.pdf" \\
             -F "files=@invoice.xlsx"
    """
    # Validate batch size
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum {MAX_BATCH_FILES} files per batch."
        )

    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided. Upload at least one file."
        )

    uploaded = []
    failed = []

    # Create inbound_message for this upload batch
    upload_batch_id = str(uuid4())
    inbound_message = InboundMessage(
        org_id=current_user.org_id,
        source="UPLOAD",
        source_message_id=upload_batch_id,
        from_email=None,  # NULL for uploads
        to_email=None,  # NULL for uploads
        subject=None,  # NULL for uploads
        received_at=datetime.now(timezone.utc),
        raw_storage_key=None,  # No raw MIME for uploads
        status="STORED"  # Uploads go directly to STORED state
    )
    db.add(inbound_message)
    db.flush()  # Get inbound_message.id

    logger.info(
        f"Created inbound_message for upload batch: "
        f"id={inbound_message.id}, org_id={current_user.org_id}, "
        f"batch_id={upload_batch_id}, file_count={len(files)}"
    )

    # Process each uploaded file
    for file in files:
        try:
            # Validate filename
            is_valid, error_msg = validate_filename(file.filename)
            if not is_valid:
                failed.append(FailedUploadResponse(
                    file_name=file.filename or "unknown",
                    error=error_msg or "Invalid filename"
                ))
                continue

            # Sanitize filename
            safe_filename = sanitize_filename(file.filename)

            # Validate MIME type
            if not is_supported_mime_type(file.content_type):
                failed.append(FailedUploadResponse(
                    file_name=safe_filename,
                    error=f"Unsupported MIME type: {file.content_type}. "
                          f"Supported types: PDF, Excel (.xls, .xlsx), CSV"
                ))
                continue

            # Read file to calculate size
            file_content = await file.read()
            size_bytes = len(file_content)

            # Validate file size
            is_valid, error_msg = validate_file_size(size_bytes, MAX_FILE_SIZE)
            if not is_valid:
                failed.append(FailedUploadResponse(
                    file_name=safe_filename,
                    error=error_msg or f"File size validation failed"
                ))
                continue

            # Store file in object storage (calculates SHA256)
            # Convert bytes to file-like object
            from io import BytesIO
            file_stream = BytesIO(file_content)

            stored_file = await storage.store_file(
                file=file_stream,
                org_id=current_user.org_id,
                filename=safe_filename,
                mime_type=file.content_type
            )

            logger.info(
                f"Stored file: storage_key={stored_file.storage_key}, "
                f"sha256={stored_file.sha256}, size={stored_file.size_bytes}"
            )

            # Check if duplicate
            is_duplicate = await check_duplicate_document(
                db,
                org_id=current_user.org_id,
                sha256=stored_file.sha256,
                file_name=safe_filename,
                size_bytes=stored_file.size_bytes
            )

            # Create document record
            document = Document(
                org_id=current_user.org_id,
                inbound_message_id=inbound_message.id,
                file_name=safe_filename,
                mime_type=file.content_type,
                size_bytes=stored_file.size_bytes,
                sha256=stored_file.sha256,
                storage_key=stored_file.storage_key,
                status=DocumentStatus.STORED,  # Uploads skip UPLOADED state
                preview_storage_key=None,
                extracted_text_storage_key=None,
                page_count=None,
                text_coverage_ratio=None,
                layout_fingerprint=None,
                error_json=None
            )
            db.add(document)
            db.flush()  # Get document.id

            logger.info(
                f"Created document: id={document.id}, file_name={safe_filename}, "
                f"is_duplicate={is_duplicate}, status={document.status}"
            )

            # TODO: Enqueue extraction job
            # This will be implemented in spec 009-extraction-core
            # extract_document.delay(
            #     document_id=str(document.id),
            #     org_id=str(current_user.org_id)
            # )

            uploaded.append(UploadedDocumentResponse(
                document_id=document.id,
                file_name=safe_filename,
                size_bytes=stored_file.size_bytes,
                sha256=stored_file.sha256,
                status=document.status.value if hasattr(document.status, 'value') else document.status,
                is_duplicate=is_duplicate
            ))

        except Exception as e:
            logger.error(
                f"Upload failed for {file.filename}: {e}",
                exc_info=True
            )
            failed.append(FailedUploadResponse(
                file_name=file.filename or "unknown",
                error=str(e)
            ))

    # Commit transaction
    try:
        db.commit()
        logger.info(
            f"Upload batch complete: uploaded={len(uploaded)}, "
            f"failed={len(failed)}, org_id={current_user.org_id}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit upload batch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded documents. Please try again."
        )

    return UploadResponse(
        uploaded=uploaded,
        failed=failed
    )
