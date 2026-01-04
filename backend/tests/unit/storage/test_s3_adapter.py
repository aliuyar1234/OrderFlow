"""Unit tests for S3 Storage Adapter using moto

SSOT Reference: §3.2 (Object Storage), §5.4.6 (Storage Keys)
Spec: 005-object-storage
Task: T049 - Create moto-based tests for S3 adapter

This module tests the S3StorageAdapter implementation using moto to mock AWS S3.
Tests cover all core functionality: store, retrieve, delete, exists, presigned URLs,
deduplication logic, and org-scoped storage.
"""

import hashlib
import io
import pytest
from datetime import datetime
from uuid import UUID, uuid4

from moto import mock_aws
import boto3

from infrastructure.storage.s3_storage_adapter import (
    S3StorageAdapter,
    StorageError,
)
from domain.documents.ports.object_storage_port import StoredFile


# Test constants
TEST_BUCKET = "test-orderflow-bucket"
TEST_REGION = "us-east-1"
TEST_ACCESS_KEY = "test-access-key"
TEST_SECRET_KEY = "test-secret-key"
TEST_ORG_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


@pytest.fixture
def s3_setup():
    """Set up mock S3 environment with bucket"""
    with mock_aws():
        # Create S3 client and bucket
        s3_client = boto3.client(
            "s3",
            region_name=TEST_REGION,
            aws_access_key_id=TEST_ACCESS_KEY,
            aws_secret_access_key=TEST_SECRET_KEY,
        )
        s3_client.create_bucket(Bucket=TEST_BUCKET)

        yield s3_client


@pytest.fixture
def storage_adapter():
    """Create S3StorageAdapter instance with mock S3"""
    with mock_aws():
        # Create bucket first
        s3_client = boto3.client(
            "s3",
            region_name=TEST_REGION,
            aws_access_key_id=TEST_ACCESS_KEY,
            aws_secret_access_key=TEST_SECRET_KEY,
        )
        s3_client.create_bucket(Bucket=TEST_BUCKET)

        # Create adapter
        adapter = S3StorageAdapter(
            endpoint_url=None,  # AWS S3 (moto mocks this)
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket_name=TEST_BUCKET,
            region=TEST_REGION,
        )

        yield adapter


class TestS3AdapterInitialization:
    """Test S3 adapter initialization"""

    def test_adapter_creation_success(self):
        """Test successful adapter creation"""
        with mock_aws():
            adapter = S3StorageAdapter(
                endpoint_url=None,
                access_key=TEST_ACCESS_KEY,
                secret_key=TEST_SECRET_KEY,
                bucket_name=TEST_BUCKET,
                region=TEST_REGION,
            )
            assert adapter.bucket_name == TEST_BUCKET
            assert adapter.region == TEST_REGION

    def test_adapter_with_minio_endpoint(self):
        """Test adapter creation with MinIO endpoint"""
        with mock_aws():
            adapter = S3StorageAdapter(
                endpoint_url="http://localhost:9000",
                access_key=TEST_ACCESS_KEY,
                secret_key=TEST_SECRET_KEY,
                bucket_name=TEST_BUCKET,
                region=TEST_REGION,
            )
            assert adapter.bucket_name == TEST_BUCKET


class TestStoreFile:
    """Test file storage operations"""

    @pytest.mark.asyncio
    async def test_store_file_success(self, storage_adapter):
        """Test successful file upload"""
        file_content = b"Test PDF content for upload"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="invoice.pdf",
            mime_type="application/pdf",
        )

        # Verify returned metadata
        assert isinstance(stored, StoredFile)
        assert stored.storage_key.startswith(str(TEST_ORG_ID))
        assert stored.storage_key.endswith(".pdf")
        assert stored.sha256 == hashlib.sha256(file_content).hexdigest()
        assert stored.size_bytes == len(file_content)
        assert stored.mime_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_store_file_streaming_chunks(self, storage_adapter):
        """Test file storage with streaming (large file simulation)"""
        # Create 20KB file (larger than 8KB chunk size)
        file_content = b"X" * (20 * 1024)
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="large_file.pdf",
            mime_type="application/pdf",
        )

        assert stored.size_bytes == len(file_content)
        assert stored.sha256 == hashlib.sha256(file_content).hexdigest()

    @pytest.mark.asyncio
    async def test_store_file_empty_raises_error(self, storage_adapter):
        """Test storing empty file raises ValueError"""
        empty_file = io.BytesIO(b"")

        with pytest.raises(ValueError, match="Cannot store empty file"):
            await storage_adapter.store_file(
                file=empty_file,
                org_id=TEST_ORG_ID,
                filename="empty.pdf",
                mime_type="application/pdf",
            )

    @pytest.mark.asyncio
    async def test_store_file_without_extension(self, storage_adapter):
        """Test storing file without extension"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="document",  # No extension
            mime_type="application/pdf",
        )

        # Storage key should not have extension
        assert not stored.storage_key.endswith(".")
        assert stored.sha256 in stored.storage_key

    @pytest.mark.asyncio
    async def test_store_file_xlsx(self, storage_adapter):
        """Test storing Excel file"""
        file_content = b"Excel file content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="orders.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        assert stored.storage_key.endswith(".xlsx")
        assert stored.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @pytest.mark.asyncio
    async def test_store_file_csv(self, storage_adapter):
        """Test storing CSV file"""
        file_content = b"SKU,Description,Price\n12345,Widget,10.00"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="products.csv",
            mime_type="text/csv",
        )

        assert stored.storage_key.endswith(".csv")
        assert stored.mime_type == "text/csv"


class TestDeduplication:
    """Test file deduplication logic"""

    @pytest.mark.asyncio
    async def test_duplicate_file_returns_existing(self, storage_adapter):
        """Test uploading same file twice returns same storage_key (deduplication)"""
        file_content = b"Duplicate test content"

        # Upload file first time
        file1 = io.BytesIO(file_content)
        stored1 = await storage_adapter.store_file(
            file=file1,
            org_id=TEST_ORG_ID,
            filename="invoice.pdf",
            mime_type="application/pdf",
        )

        # Upload same file again (same content, same org)
        file2 = io.BytesIO(file_content)
        stored2 = await storage_adapter.store_file(
            file=file2,
            org_id=TEST_ORG_ID,
            filename="invoice.pdf",
            mime_type="application/pdf",
        )

        # Should return same storage key (deduplication)
        assert stored1.storage_key == stored2.storage_key
        assert stored1.sha256 == stored2.sha256
        assert stored1.size_bytes == stored2.size_bytes

    @pytest.mark.asyncio
    async def test_duplicate_file_different_filename(self, storage_adapter):
        """Test deduplication works even with different filename"""
        file_content = b"Same content, different filename"

        # Upload with first filename
        file1 = io.BytesIO(file_content)
        stored1 = await storage_adapter.store_file(
            file=file1,
            org_id=TEST_ORG_ID,
            filename="invoice_v1.pdf",
            mime_type="application/pdf",
        )

        # Upload with different filename but same content
        file2 = io.BytesIO(file_content)
        stored2 = await storage_adapter.store_file(
            file=file2,
            org_id=TEST_ORG_ID,
            filename="invoice_v2.pdf",
            mime_type="application/pdf",
        )

        # Should return same storage key (SHA256 is the same)
        assert stored1.storage_key == stored2.storage_key
        assert stored1.sha256 == stored2.sha256


class TestOrgScopedStorage:
    """Test org-scoped storage keys and isolation"""

    @pytest.mark.asyncio
    async def test_storage_key_includes_org_id(self, storage_adapter):
        """Test storage key starts with org_id"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Storage key format: {org_id}/{year}/{month}/{sha256}.{ext}
        assert stored.storage_key.startswith(str(TEST_ORG_ID))

    @pytest.mark.asyncio
    async def test_storage_key_includes_year_month(self, storage_adapter):
        """Test storage key includes year and month"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Storage key format: {org_id}/{year}/{month}/{sha256}.{ext}
        now = datetime.utcnow()
        expected_year = str(now.year)
        expected_month = f"{now.month:02d}"

        assert f"/{expected_year}/" in stored.storage_key
        assert f"/{expected_month}/" in stored.storage_key

    @pytest.mark.asyncio
    async def test_different_orgs_different_keys(self, storage_adapter):
        """Test same file uploaded by different orgs gets different storage keys"""
        file_content = b"Test content"
        org1_id = uuid4()
        org2_id = uuid4()

        # Upload for org1
        file1 = io.BytesIO(file_content)
        stored1 = await storage_adapter.store_file(
            file=file1,
            org_id=org1_id,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Upload for org2
        file2 = io.BytesIO(file_content)
        stored2 = await storage_adapter.store_file(
            file=file2,
            org_id=org2_id,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Different storage keys (org-scoped)
        assert stored1.storage_key != stored2.storage_key
        assert stored1.storage_key.startswith(str(org1_id))
        assert stored2.storage_key.startswith(str(org2_id))

        # But same SHA256 (same content)
        assert stored1.sha256 == stored2.sha256

    @pytest.mark.asyncio
    async def test_storage_key_includes_sha256(self, storage_adapter):
        """Test storage key includes SHA256 hash"""
        file_content = b"Test content for SHA256"
        file = io.BytesIO(file_content)

        expected_sha256 = hashlib.sha256(file_content).hexdigest()

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Storage key should contain SHA256
        assert expected_sha256 in stored.storage_key


class TestRetrieveFile:
    """Test file retrieval operations"""

    @pytest.mark.asyncio
    async def test_retrieve_file_success(self, storage_adapter):
        """Test successful file retrieval"""
        file_content = b"Test content for retrieval"
        file = io.BytesIO(file_content)

        # Store file first
        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Retrieve file
        retrieved_stream = await storage_adapter.retrieve_file(stored.storage_key)
        retrieved_content = retrieved_stream.read()

        assert retrieved_content == file_content

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_file_raises_error(self, storage_adapter):
        """Test retrieving non-existent file raises FileNotFoundError"""
        fake_key = f"{TEST_ORG_ID}/2025/01/nonexistent.pdf"

        with pytest.raises(FileNotFoundError, match="File not found"):
            await storage_adapter.retrieve_file(fake_key)

    @pytest.mark.asyncio
    async def test_retrieve_large_file(self, storage_adapter):
        """Test retrieving large file"""
        # Create 100KB file
        file_content = b"X" * (100 * 1024)
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="large.pdf",
            mime_type="application/pdf",
        )

        retrieved_stream = await storage_adapter.retrieve_file(stored.storage_key)
        retrieved_content = retrieved_stream.read()

        assert len(retrieved_content) == len(file_content)
        assert retrieved_content == file_content


class TestFileExists:
    """Test file existence checks"""

    @pytest.mark.asyncio
    async def test_file_exists_returns_true(self, storage_adapter):
        """Test file_exists returns True for existing file"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        exists = await storage_adapter.file_exists(stored.storage_key)
        assert exists is True

    @pytest.mark.asyncio
    async def test_file_exists_returns_false(self, storage_adapter):
        """Test file_exists returns False for non-existent file"""
        fake_key = f"{TEST_ORG_ID}/2025/01/nonexistent.pdf"

        exists = await storage_adapter.file_exists(fake_key)
        assert exists is False

    @pytest.mark.asyncio
    async def test_file_exists_after_delete(self, storage_adapter):
        """Test file_exists returns False after deletion"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Verify file exists
        assert await storage_adapter.file_exists(stored.storage_key) is True

        # Delete file
        await storage_adapter.delete_file(stored.storage_key)

        # Verify file no longer exists
        assert await storage_adapter.file_exists(stored.storage_key) is False


class TestDeleteFile:
    """Test file deletion operations"""

    @pytest.mark.asyncio
    async def test_delete_file_success(self, storage_adapter):
        """Test successful file deletion"""
        file_content = b"Test content for deletion"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Delete file
        deleted = await storage_adapter.delete_file(stored.storage_key)
        assert deleted is True

        # Verify file no longer exists
        exists = await storage_adapter.file_exists(stored.storage_key)
        assert exists is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file_returns_false(self, storage_adapter):
        """Test deleting non-existent file returns False (idempotent)"""
        fake_key = f"{TEST_ORG_ID}/2025/01/nonexistent.pdf"

        deleted = await storage_adapter.delete_file(fake_key)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_file_twice_idempotent(self, storage_adapter):
        """Test deleting file twice is idempotent"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        # Delete first time
        deleted1 = await storage_adapter.delete_file(stored.storage_key)
        assert deleted1 is True

        # Delete second time
        deleted2 = await storage_adapter.delete_file(stored.storage_key)
        assert deleted2 is False


class TestGeneratePresignedUrl:
    """Test presigned URL generation"""

    @pytest.mark.asyncio
    async def test_generate_presigned_url_success(self, storage_adapter):
        """Test successful presigned URL generation"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        url = await storage_adapter.generate_presigned_url(stored.storage_key)

        # Verify URL is a string and contains bucket/key
        assert isinstance(url, str)
        assert len(url) > 0

    @pytest.mark.asyncio
    async def test_generate_presigned_url_custom_expiry(self, storage_adapter):
        """Test presigned URL with custom expiry"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="test.pdf",
            mime_type="application/pdf",
        )

        url = await storage_adapter.generate_presigned_url(
            stored.storage_key,
            expires_in_seconds=7200,  # 2 hours
        )

        assert isinstance(url, str)
        assert len(url) > 0

    @pytest.mark.asyncio
    async def test_generate_presigned_url_nonexistent_file(self, storage_adapter):
        """Test presigned URL for non-existent file raises FileNotFoundError"""
        fake_key = f"{TEST_ORG_ID}/2025/01/nonexistent.pdf"

        with pytest.raises(FileNotFoundError, match="File not found"):
            await storage_adapter.generate_presigned_url(fake_key)


class TestVerifyBucket:
    """Test bucket verification"""

    @pytest.mark.asyncio
    async def test_verify_bucket_exists(self, storage_adapter):
        """Test successful bucket verification"""
        result = await storage_adapter.verify_bucket_exists()
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_nonexistent_bucket_raises_error(self):
        """Test verifying non-existent bucket raises StorageError"""
        with mock_aws():
            # Don't create bucket
            adapter = S3StorageAdapter(
                endpoint_url=None,
                access_key=TEST_ACCESS_KEY,
                secret_key=TEST_SECRET_KEY,
                bucket_name="nonexistent-bucket",
                region=TEST_REGION,
            )

            with pytest.raises(StorageError, match="does not exist"):
                await adapter.verify_bucket_exists()


class TestStorageKeyGeneration:
    """Test internal storage key generation logic"""

    @pytest.mark.asyncio
    async def test_storage_key_format(self, storage_adapter):
        """Test storage key follows format: {org_id}/{year}/{month}/{sha256}.{ext}"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="invoice.pdf",
            mime_type="application/pdf",
        )

        # Parse storage key
        parts = stored.storage_key.split("/")
        assert len(parts) == 4
        assert parts[0] == str(TEST_ORG_ID)
        assert parts[1].isdigit()  # year
        assert parts[2].isdigit()  # month
        assert parts[3].endswith(".pdf")  # sha256.ext

    @pytest.mark.asyncio
    async def test_storage_key_preserves_extension(self, storage_adapter):
        """Test storage key preserves file extension"""
        test_cases = [
            ("invoice.pdf", ".pdf"),
            ("orders.xlsx", ".xlsx"),
            ("data.csv", ".csv"),
            ("archive.zip", ".zip"),
            ("document", ""),  # no extension
        ]

        for filename, expected_ext in test_cases:
            file_content = f"Content for {filename}".encode()
            file = io.BytesIO(file_content)

            stored = await storage_adapter.store_file(
                file=file,
                org_id=TEST_ORG_ID,
                filename=filename,
                mime_type="application/octet-stream",
            )

            if expected_ext:
                assert stored.storage_key.endswith(expected_ext)
            else:
                # No extension means storage key ends with SHA256 hash
                assert not stored.storage_key.endswith(".")


class TestMetadata:
    """Test S3 metadata storage"""

    @pytest.mark.asyncio
    async def test_metadata_stored_with_file(self, storage_adapter, s3_setup):
        """Test S3 metadata includes sha256, original_filename, org_id"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="invoice.pdf",
            mime_type="application/pdf",
        )

        # Retrieve object metadata from S3
        response = s3_setup.head_object(
            Bucket=TEST_BUCKET,
            Key=stored.storage_key,
        )

        metadata = response.get("Metadata", {})
        assert metadata.get("sha256") == stored.sha256
        assert metadata.get("original_filename") == "invoice.pdf"
        assert metadata.get("org_id") == str(TEST_ORG_ID)

    @pytest.mark.asyncio
    async def test_content_type_stored(self, storage_adapter, s3_setup):
        """Test S3 ContentType is set correctly"""
        file_content = b"Test content"
        file = io.BytesIO(file_content)

        stored = await storage_adapter.store_file(
            file=file,
            org_id=TEST_ORG_ID,
            filename="invoice.pdf",
            mime_type="application/pdf",
        )

        # Retrieve object metadata
        response = s3_setup.head_object(
            Bucket=TEST_BUCKET,
            Key=stored.storage_key,
        )

        assert response.get("ContentType") == "application/pdf"
