"""Document storage API endpoints.

Provides REST API for uploading, downloading, and managing documents in object storage.

SSOT Reference: §6.9 (Document Endpoints)
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database import get_db
from infrastructure.storage.s3_storage_adapter import (
    S3StorageAdapter,
    StorageError,
)
from infrastructure.storage.storage_config import (
    load_storage_config_from_env,
)
from models.document import Document, DocumentStatus
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# Storage adapter singleton (initialized once)
_storage_adapter: Optional[S3StorageAdapter] = None


def get_storage_adapter() -> S3StorageAdapter:
    """Get or create storage adapter singleton.

    Returns:
        S3StorageAdapter: Configured storage adapter

    Raises:
        HTTPException: If storage configuration is invalid
    """
    global _storage_adapter

    if _storage_adapter is None:
        try:
            config = load_storage_config_from_env()
            _storage_adapter = S3StorageAdapter(
                endpoint_url=config.endpoint_url,
                access_key=config.access_key,
                secret_key=config.secret_key,
                bucket_name=config.bucket_name,
                region=config.region,
            )
            logger.info("Initialized storage adapter")
        except Exception as e:
            logger.error(f"Failed to initialize storage adapter: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Storage configuration error: {str(e)}",
            )

    return _storage_adapter


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
):
    """Upload a document to object storage.

    This endpoint:
    1. Validates file upload
    2. Stores file in S3/MinIO (with deduplication)
    3. Creates document record in database
    4. Returns document metadata

    Args:
        file: Uploaded file (multipart/form-data)
        db: Database session
        current_user: Authenticated user
        storage: Storage adapter

    Returns:
        dict: Document metadata with storage_key

    Raises:
        HTTPException: If upload fails or validation errors
    """
    org_id = current_user.org_id

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required",
        )

    # Validate MIME type
    allowed_mime_types = [
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    ]

    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {mime_type}. "
            f"Allowed: PDF, Excel, CSV",
        )

    try:
        # Store file in object storage
        stored_file = await storage.store_file(
            file=file.file,
            org_id=org_id,
            filename=file.filename,
            mime_type=mime_type,
        )

        # Check if document already exists (deduplication)
        existing_doc = (
            db.query(Document)
            .filter(
                Document.org_id == org_id,
                Document.sha256 == stored_file.sha256,
                Document.file_name == file.filename,
                Document.size_bytes == stored_file.size_bytes,
            )
            .first()
        )

        if existing_doc:
            logger.info(
                f"Document already exists (dedup): id={existing_doc.id}, "
                f"sha256={stored_file.sha256}"
            )
            return {
                "id": str(existing_doc.id),
                "org_id": str(existing_doc.org_id),
                "file_name": existing_doc.file_name,
                "mime_type": existing_doc.mime_type,
                "size_bytes": existing_doc.size_bytes,
                "sha256": existing_doc.sha256,
                "storage_key": existing_doc.storage_key,
                "status": existing_doc.status.value,
                "created_at": existing_doc.created_at.isoformat(),
                "deduplication": True,
            }

        # Create new document record
        document = Document(
            org_id=org_id,
            file_name=file.filename,
            mime_type=mime_type,
            size_bytes=stored_file.size_bytes,
            sha256=stored_file.sha256,
            storage_key=stored_file.storage_key,
            status=DocumentStatus.STORED,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        logger.info(
            f"Document uploaded: id={document.id}, "
            f"storage_key={stored_file.storage_key}, "
            f"size={stored_file.size_bytes}"
        )

        return {
            "id": str(document.id),
            "org_id": str(document.org_id),
            "file_name": document.file_name,
            "mime_type": document.mime_type,
            "size_bytes": document.size_bytes,
            "sha256": document.sha256,
            "storage_key": document.storage_key,
            "status": document.status.value,
            "created_at": document.created_at.isoformat(),
            "deduplication": False,
        }

    except StorageError as e:
        logger.error(f"Storage error during upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
):
    """Download a document from object storage.

    Args:
        document_id: Document UUID
        db: Database session
        current_user: Authenticated user
        storage: Storage adapter

    Returns:
        StreamingResponse: File content with appropriate headers

    Raises:
        HTTPException: If document not found or access denied
    """
    org_id = current_user.org_id

    # Fetch document (with tenant isolation)
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.org_id == org_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        # Retrieve file from storage
        file_stream = await storage.retrieve_file(document.storage_key)

        logger.info(
            f"Document downloaded: id={document_id}, "
            f"storage_key={document.storage_key}"
        )

        return StreamingResponse(
            file_stream,
            media_type=document.mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{document.file_name}"'
            },
        )

    except FileNotFoundError:
        logger.error(
            f"File not found in storage: id={document_id}, "
            f"storage_key={document.storage_key}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )
    except StorageError as e:
        logger.error(f"Storage error during download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}",
        )


@router.get("/{document_id}/presigned-url")
async def get_presigned_url(
    document_id: UUID,
    expires_in: int = 3600,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
):
    """Generate a presigned URL for direct download from object storage.

    Presigned URLs allow clients to download files directly from S3/MinIO
    without going through the application server.

    Args:
        document_id: Document UUID
        expires_in: URL expiration time in seconds (default: 1 hour, max: 7 days)
        db: Database session
        current_user: Authenticated user
        storage: Storage adapter

    Returns:
        dict: Presigned URL and expiration time

    Raises:
        HTTPException: If document not found or access denied
    """
    org_id = current_user.org_id

    # Validate expiration time
    max_expiry = 7 * 24 * 3600  # 7 days
    if expires_in < 60 or expires_in > max_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expiration must be between 60 and {max_expiry} seconds",
        )

    # Fetch document (with tenant isolation)
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.org_id == org_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        # Generate presigned URL
        presigned_url = await storage.generate_presigned_url(
            storage_key=document.storage_key,
            expires_in_seconds=expires_in,
        )

        logger.info(
            f"Presigned URL generated: id={document_id}, "
            f"expires_in={expires_in}s"
        )

        return {
            "url": presigned_url,
            "expires_in_seconds": expires_in,
            "document_id": str(document_id),
            "file_name": document.file_name,
        }

    except FileNotFoundError:
        logger.error(
            f"File not found in storage: id={document_id}, "
            f"storage_key={document.storage_key}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )
    except StorageError as e:
        logger.error(f"Storage error generating presigned URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}",
        )


@router.get("/{document_id}")
async def get_document_metadata(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get document metadata.

    Args:
        document_id: Document UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        dict: Document metadata

    Raises:
        HTTPException: If document not found or access denied
    """
    org_id = current_user.org_id

    # Fetch document (with tenant isolation)
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.org_id == org_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return {
        "id": str(document.id),
        "org_id": str(document.org_id),
        "file_name": document.file_name,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256,
        "storage_key": document.storage_key,
        "preview_storage_key": document.preview_storage_key,
        "status": document.status.value,
        "page_count": document.page_count,
        "text_coverage_ratio": (
            float(document.text_coverage_ratio)
            if document.text_coverage_ratio
            else None
        ),
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }
