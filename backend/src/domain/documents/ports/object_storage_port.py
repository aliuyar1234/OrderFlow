"""Object Storage Port - Domain interface for S3-compatible storage.

This port defines the contract for storing and retrieving files in object storage.
Adapters must implement this interface to provide S3, MinIO, or other storage backends.

SSOT Reference: §3.2 (Object Storage), §5.4.6 (document.storage_key)
Architecture: Hexagonal - Port interface in domain layer
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO, Optional
from uuid import UUID


@dataclass
class StoredFile:
    """Metadata for a file stored in object storage.

    Attributes:
        storage_key: Unique key in object storage (format: {org_id}/{year}/{month}/{sha256}.{ext})
        sha256: SHA256 hash of file content (hex format)
        size_bytes: File size in bytes
        mime_type: MIME type of the file (e.g., 'application/pdf')
    """
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str


class ObjectStoragePort(ABC):
    """Port interface for S3-compatible object storage operations.

    This interface defines the contract for storing, retrieving, and managing files
    in object storage. Implementations must provide S3-compatible storage (AWS S3, MinIO, etc.).

    Key Design Principles:
    - Storage keys include org_id for multi-tenant isolation (SSOT §5.1)
    - SHA256 calculated during upload for deduplication and integrity
    - Streaming support for large files (>100MB)
    - Idempotent operations (store_file returns existing if duplicate)

    Example Usage:
        storage = S3StorageAdapter(...)

        # Store a file
        with open('invoice.pdf', 'rb') as f:
            stored = await storage.store_file(
                file=f,
                org_id=UUID('...'),
                filename='invoice.pdf',
                mime_type='application/pdf'
            )

        # Retrieve a file
        file_stream = await storage.retrieve_file(stored.storage_key)
    """

    @abstractmethod
    async def store_file(
        self,
        file: BinaryIO,
        org_id: UUID,
        filename: str,
        mime_type: str,
    ) -> StoredFile:
        """Store a file in object storage with automatic deduplication.

        This method:
        1. Calculates SHA256 hash while reading the file
        2. Generates storage key: {org_id}/{year}/{month}/{sha256}.{ext}
        3. Checks if file already exists (same SHA256 for this org)
        4. If exists: returns existing StoredFile (deduplication)
        5. If new: uploads file and returns new StoredFile

        Args:
            file: Binary file stream to store (must be readable)
            org_id: Organization UUID (for multi-tenant isolation)
            filename: Original filename (for extension extraction)
            mime_type: MIME type of the file

        Returns:
            StoredFile: Metadata about stored file (storage_key, sha256, size, mime_type)

        Raises:
            StorageError: If upload fails or storage is unavailable
            ValueError: If file is empty or invalid

        Note:
            - File stream position is not reset after reading
            - SHA256 calculation adds <10% overhead to upload time
            - Deduplication is per-org only (not cross-tenant)
        """
        pass

    @abstractmethod
    async def retrieve_file(self, storage_key: str) -> BinaryIO:
        """Retrieve a file from object storage by its storage key.

        Args:
            storage_key: Storage key returned by store_file()

        Returns:
            BinaryIO: File stream (caller must close when done)

        Raises:
            FileNotFoundError: If file doesn't exist in storage
            StorageError: If retrieval fails

        Note:
            Caller is responsible for closing the returned stream.
        """
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Delete a file from object storage.

        Args:
            storage_key: Storage key of file to delete

        Returns:
            bool: True if file was deleted, False if it didn't exist

        Raises:
            StorageError: If deletion fails

        Note:
            This operation is idempotent (deleting non-existent file returns False).
        """
        pass

    @abstractmethod
    async def file_exists(self, storage_key: str) -> bool:
        """Check if a file exists in object storage.

        Args:
            storage_key: Storage key to check

        Returns:
            bool: True if file exists, False otherwise

        Note:
            This is faster than retrieving the file (only HEAD request).
        """
        pass

    @abstractmethod
    async def generate_presigned_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        """Generate a presigned URL for secure direct download.

        Presigned URLs allow clients to download files directly from object storage
        without going through the application server, reducing bandwidth and latency.

        Args:
            storage_key: Storage key of file to generate URL for
            expires_in_seconds: URL expiration time (default: 1 hour)

        Returns:
            str: Presigned URL (valid for expires_in_seconds)

        Raises:
            FileNotFoundError: If file doesn't exist
            StorageError: If URL generation fails

        Note:
            URLs are time-limited and expire after the specified duration.
        """
        pass
