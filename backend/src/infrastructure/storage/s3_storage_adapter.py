"""S3 Storage Adapter - Implementation of ObjectStoragePort using boto3.

Provides S3-compatible storage operations for AWS S3, MinIO, and other S3-compatible services.
Implements deduplication, streaming uploads, and presigned URLs.

SSOT Reference: §3.2 (Object Storage), §5.4.6 (Storage Keys)
Architecture: Hexagonal - Adapter implementation in infrastructure layer
"""

import hashlib
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import UUID

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from domain.documents.ports.object_storage_port import (
    ObjectStoragePort,
    StoredFile,
)

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class S3StorageAdapter(ObjectStoragePort):
    """S3-compatible storage adapter using boto3.

    This adapter implements the ObjectStoragePort interface using boto3 to interact
    with S3-compatible storage (AWS S3, MinIO, etc.).

    Features:
    - SHA256-based deduplication (per-org)
    - Streaming uploads for large files
    - Presigned URLs for direct downloads
    - Storage key format: {org_id}/{year}/{month}/{sha256}.{ext}

    Example:
        config = load_storage_config_from_env()
        storage = S3StorageAdapter(
            endpoint_url=config.endpoint_url,
            access_key=config.access_key,
            secret_key=config.secret_key,
            bucket_name=config.bucket_name,
            region=config.region,
        )

        # Store file
        with open('document.pdf', 'rb') as f:
            stored = await storage.store_file(
                file=f,
                org_id=UUID('...'),
                filename='document.pdf',
                mime_type='application/pdf',
            )
    """

    def __init__(
        self,
        endpoint_url: Optional[str],
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = "us-east-1",
    ):
        """Initialize S3 storage adapter.

        Args:
            endpoint_url: S3 endpoint URL (None for AWS S3, URL for MinIO)
            access_key: S3 access key ID
            secret_key: S3 secret access key
            bucket_name: S3 bucket name
            region: AWS region (default: 'us-east-1')

        Raises:
            StorageError: If S3 client initialization fails
        """
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            self.bucket_name = bucket_name
            self.region = region

            logger.info(
                f"Initialized S3 storage adapter: bucket={bucket_name}, "
                f"endpoint={endpoint_url or 'AWS S3'}, region={region}"
            )
        except NoCredentialsError as e:
            raise StorageError(f"Invalid S3 credentials: {e}")
        except Exception as e:
            raise StorageError(f"Failed to initialize S3 client: {e}")

    async def store_file(
        self,
        file: BinaryIO,
        org_id: UUID,
        filename: str,
        mime_type: str,
    ) -> StoredFile:
        """Store a file in S3 with automatic deduplication.

        Implementation:
        1. Reads file in chunks (8KB) while calculating SHA256
        2. Generates storage key: {org_id}/{year}/{month}/{sha256}.{ext}
        3. Checks if file exists (deduplication)
        4. Uploads if new, returns existing if duplicate

        Args:
            file: Binary file stream
            org_id: Organization UUID
            filename: Original filename
            mime_type: MIME type

        Returns:
            StoredFile: Metadata about stored file

        Raises:
            StorageError: If upload fails
            ValueError: If file is empty
        """
        # Calculate SHA256 while reading file
        sha256_hash = hashlib.sha256()
        chunks = []
        size_bytes = 0

        chunk_size = 8192  # 8KB chunks
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            sha256_hash.update(chunk)
            chunks.append(chunk)
            size_bytes += len(chunk)

        if size_bytes == 0:
            raise ValueError("Cannot store empty file")

        sha256_hex = sha256_hash.hexdigest()

        # Generate storage key
        storage_key = self._generate_storage_key(
            org_id=org_id,
            sha256=sha256_hex,
            filename=filename,
        )

        # Check if file already exists (deduplication)
        if await self.file_exists(storage_key):
            logger.info(
                f"File already exists (dedup): storage_key={storage_key}, "
                f"sha256={sha256_hex}, size={size_bytes}"
            )
            return StoredFile(
                storage_key=storage_key,
                sha256=sha256_hex,
                size_bytes=size_bytes,
                mime_type=mime_type,
            )

        # Upload file to S3
        try:
            file_content = b"".join(chunks)
            file_stream = BytesIO(file_content)

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_key,
                Body=file_stream,
                ContentType=mime_type,
                Metadata={
                    "sha256": sha256_hex,
                    "original_filename": filename,
                    "org_id": str(org_id),
                },
            )

            logger.info(
                f"Uploaded file: storage_key={storage_key}, "
                f"sha256={sha256_hex}, size={size_bytes}, mime_type={mime_type}"
            )

            return StoredFile(
                storage_key=storage_key,
                sha256=sha256_hex,
                size_bytes=size_bytes,
                mime_type=mime_type,
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"S3 upload failed: storage_key={storage_key}, "
                f"error={error_code}, message={e}"
            )
            raise StorageError(f"Failed to upload file: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            raise StorageError(f"Failed to upload file: {e}")

    async def retrieve_file(self, storage_key: str) -> BinaryIO:
        """Retrieve a file from S3.

        Args:
            storage_key: Storage key of file to retrieve

        Returns:
            BinaryIO: File stream (caller must close)

        Raises:
            FileNotFoundError: If file doesn't exist
            StorageError: If retrieval fails
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )

            logger.info(f"Retrieved file: storage_key={storage_key}")
            return response["Body"]

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.warning(f"File not found: storage_key={storage_key}")
                raise FileNotFoundError(f"File not found: {storage_key}")
            logger.error(
                f"S3 retrieval failed: storage_key={storage_key}, "
                f"error={error_code}"
            )
            raise StorageError(f"Failed to retrieve file: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error during retrieval: {e}")
            raise StorageError(f"Failed to retrieve file: {e}")

    async def delete_file(self, storage_key: str) -> bool:
        """Delete a file from S3.

        Args:
            storage_key: Storage key of file to delete

        Returns:
            bool: True if deleted, False if didn't exist

        Raises:
            StorageError: If deletion fails
        """
        try:
            # Check if file exists first
            exists = await self.file_exists(storage_key)
            if not exists:
                logger.info(f"File not found for deletion: storage_key={storage_key}")
                return False

            # Delete the file
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )

            logger.info(f"Deleted file: storage_key={storage_key}")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"S3 deletion failed: storage_key={storage_key}, "
                f"error={error_code}"
            )
            raise StorageError(f"Failed to delete file: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error during deletion: {e}")
            raise StorageError(f"Failed to delete file: {e}")

    async def file_exists(self, storage_key: str) -> bool:
        """Check if a file exists in S3.

        Uses HEAD request (faster than GET).

        Args:
            storage_key: Storage key to check

        Returns:
            bool: True if exists, False otherwise
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                return False
            # Other errors should be logged but we'll return False
            logger.warning(
                f"Error checking file existence: storage_key={storage_key}, "
                f"error={error_code}"
            )
            return False
        except Exception:
            # Network errors, etc.
            return False

    async def generate_presigned_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        """Generate a presigned URL for direct download.

        Args:
            storage_key: Storage key of file
            expires_in_seconds: URL expiration (default: 1 hour)

        Returns:
            str: Presigned URL

        Raises:
            FileNotFoundError: If file doesn't exist
            StorageError: If URL generation fails
        """
        try:
            # Check if file exists first
            if not await self.file_exists(storage_key):
                raise FileNotFoundError(f"File not found: {storage_key}")

            # Generate presigned URL
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": storage_key,
                },
                ExpiresIn=expires_in_seconds,
            )

            logger.info(
                f"Generated presigned URL: storage_key={storage_key}, "
                f"expires_in={expires_in_seconds}s"
            )
            return url

        except FileNotFoundError:
            raise
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"Presigned URL generation failed: storage_key={storage_key}, "
                f"error={error_code}"
            )
            raise StorageError(f"Failed to generate presigned URL: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            raise StorageError(f"Failed to generate presigned URL: {e}")

    def _generate_storage_key(
        self,
        org_id: UUID,
        sha256: str,
        filename: str,
    ) -> str:
        """Generate storage key in format: {org_id}/{year}/{month}/{sha256}.{ext}

        Args:
            org_id: Organization UUID
            sha256: SHA256 hash (hex)
            filename: Original filename (for extension)

        Returns:
            str: Storage key

        Example:
            >>> _generate_storage_key(
            ...     org_id=UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890'),
            ...     sha256='abc123...',
            ...     filename='invoice.pdf'
            ... )
            'a1b2c3d4-e5f6-7890-abcd-ef1234567890/2025/12/abc123....pdf'
        """
        now = datetime.utcnow()
        year = now.year
        month = f"{now.month:02d}"

        # Extract file extension
        ext = Path(filename).suffix or ""

        # Build storage key
        storage_key = f"{org_id}/{year}/{month}/{sha256}{ext}"

        return storage_key

    async def verify_bucket_exists(self) -> bool:
        """Verify that the configured bucket exists.

        This should be called on application startup to fail fast if
        bucket doesn't exist.

        Returns:
            bool: True if bucket exists

        Raises:
            StorageError: If bucket check fails or bucket doesn't exist
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Verified bucket exists: {self.bucket_name}")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                raise StorageError(
                    f"Bucket '{self.bucket_name}' does not exist. "
                    f"Create it first or update MINIO_BUCKET environment variable."
                )
            raise StorageError(f"Failed to verify bucket: {error_code}")
        except Exception as e:
            raise StorageError(f"Failed to verify bucket: {e}")
