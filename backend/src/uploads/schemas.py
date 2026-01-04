"""Upload API request/response schemas

SSOT Reference: §8.5 (Upload API)
Spec: 007-document-upload
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


class UploadedDocumentResponse(BaseModel):
    """Response for a single uploaded document"""
    document_id: UUID = Field(..., description="UUID of created document")
    file_name: str = Field(..., description="Original filename")
    size_bytes: int = Field(..., description="File size in bytes")
    sha256: str = Field(..., description="SHA256 hash (hex format)")
    status: str = Field(..., description="Document processing status")
    is_duplicate: bool = Field(..., description="Whether file already existed (deduplicated)")

    class Config:
        from_attributes = True


class FailedUploadResponse(BaseModel):
    """Response for a failed upload"""
    file_name: str = Field(..., description="Original filename")
    error: str = Field(..., description="Error message")


class UploadResponse(BaseModel):
    """Response for upload endpoint"""
    uploaded: List[UploadedDocumentResponse] = Field(..., description="Successfully uploaded documents")
    failed: List[FailedUploadResponse] = Field(..., description="Failed uploads")

    class Config:
        from_attributes = True


class UploadErrorResponse(BaseModel):
    """Error response for upload validation failures"""
    code: str = Field(..., description="Error code (e.g., VALIDATION_ERROR, FILE_TOO_LARGE)")
    message: str = Field(..., description="Human-readable error message")
    max_size_bytes: Optional[int] = Field(None, description="Maximum allowed file size (for FILE_TOO_LARGE errors)")
    details: Optional[List[dict]] = Field(None, description="Detailed error information")

    class Config:
        from_attributes = True
