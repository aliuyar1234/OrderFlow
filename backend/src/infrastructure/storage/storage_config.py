"""Storage configuration for S3-compatible object storage.

Loads configuration from environment variables and validates connectivity.
Supports both MinIO (development) and AWS S3 (production) with the same interface.

SSOT Reference: §10.2 (Environment Variables)
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class StorageConfig:
    """Configuration for S3-compatible object storage.

    Attributes:
        endpoint_url: S3 endpoint URL (e.g., 'http://localhost:9000' for MinIO,
                      None for AWS S3 which uses default regional endpoints)
        access_key: S3 access key ID
        secret_key: S3 secret access key
        bucket_name: S3 bucket name for storing documents
        region: AWS region (default: 'us-east-1')
        use_ssl: Whether to use HTTPS (True for production, False for local MinIO)
    """
    endpoint_url: Optional[str]
    access_key: str
    secret_key: str
    bucket_name: str
    region: str = "us-east-1"
    use_ssl: bool = True


def load_storage_config_from_env() -> StorageConfig:
    """Load storage configuration from environment variables.

    Environment Variables:
        MINIO_ENDPOINT: MinIO endpoint (e.g., 'localhost:9000')
                        If not set, assumes AWS S3 with default regional endpoints
        MINIO_ROOT_USER: Access key for MinIO/S3
        MINIO_ROOT_PASSWORD: Secret key for MinIO/S3
        MINIO_BUCKET: Bucket name (default: 'orderflow-documents')
        MINIO_USE_SSL: Whether to use SSL (default: 'false' for dev, 'true' for prod)
        AWS_REGION: AWS region (default: 'us-east-1')

    Returns:
        StorageConfig: Validated storage configuration

    Raises:
        ValueError: If required environment variables are missing

    Example:
        # For MinIO (development):
        MINIO_ENDPOINT=localhost:9000
        MINIO_ROOT_USER=minioadmin
        MINIO_ROOT_PASSWORD=minioadmin
        MINIO_BUCKET=orderflow-documents
        MINIO_USE_SSL=false

        # For AWS S3 (production):
        # MINIO_ENDPOINT not set (uses AWS defaults)
        MINIO_ROOT_USER=AKIAIOSFODNN7EXAMPLE
        MINIO_ROOT_PASSWORD=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
        MINIO_BUCKET=orderflow-prod-documents
        MINIO_USE_SSL=true
        AWS_REGION=eu-central-1
    """
    # Get endpoint (None for AWS S3, URL for MinIO)
    endpoint = os.getenv("MINIO_ENDPOINT")
    endpoint_url = None
    if endpoint:
        # Build endpoint URL
        use_ssl_str = os.getenv("MINIO_USE_SSL", "false").lower()
        use_ssl = use_ssl_str in ("true", "1", "yes")
        protocol = "https" if use_ssl else "http"
        endpoint_url = f"{protocol}://{endpoint}"

    # Get credentials (required)
    access_key = os.getenv("MINIO_ROOT_USER")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD")

    if not access_key or not secret_key:
        raise ValueError(
            "Missing required storage credentials. "
            "Set MINIO_ROOT_USER and MINIO_ROOT_PASSWORD environment variables. "
            "For MinIO: use 'minioadmin' for both in development. "
            "For AWS S3: use your IAM credentials."
        )

    # Get bucket name (required)
    bucket_name = os.getenv("MINIO_BUCKET", "orderflow-documents")

    # Get region (optional, defaults to us-east-1)
    region = os.getenv("AWS_REGION", "us-east-1")

    # Determine SSL usage
    use_ssl_str = os.getenv("MINIO_USE_SSL", "false" if endpoint else "true").lower()
    use_ssl = use_ssl_str in ("true", "1", "yes")

    return StorageConfig(
        endpoint_url=endpoint_url,
        access_key=access_key,
        secret_key=secret_key,
        bucket_name=bucket_name,
        region=region,
        use_ssl=use_ssl,
    )


def validate_storage_config(config: StorageConfig) -> None:
    """Validate storage configuration.

    Args:
        config: Storage configuration to validate

    Raises:
        ValueError: If configuration is invalid
    """
    if not config.access_key:
        raise ValueError("Storage access_key is required")

    if not config.secret_key:
        raise ValueError("Storage secret_key is required")

    if not config.bucket_name:
        raise ValueError("Storage bucket_name is required")

    if config.endpoint_url:
        # MinIO configuration
        if not config.endpoint_url.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid endpoint_url: {config.endpoint_url}. "
                "Must start with http:// or https://"
            )
    else:
        # AWS S3 configuration
        if not config.region:
            raise ValueError("AWS region is required when using S3 (MINIO_ENDPOINT not set)")
