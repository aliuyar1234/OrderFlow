#!/usr/bin/env python3
"""SMTP Server Startup Script for OrderFlow.

Starts aiosmtpd server with OrderFlowSMTPHandler for receiving order emails.
Handles plus-addressing for multi-tenant routing and enqueues attachment
extraction jobs.

Usage:
    python scripts/start_smtp_server.py

Environment Variables:
    SMTP_HOST: Bind address (default: 0.0.0.0)
    SMTP_PORT: Listen port (default: 25)
    SMTP_DOMAIN: Server domain for logging (default: orderflow.example.com)
    SMTP_MAX_MESSAGE_SIZE: Max email size in bytes (default: 26214400 = 25MB)
    SMTP_MAX_CONNECTIONS: Max concurrent connections (default: 100)
    SMTP_CONNECTION_TIMEOUT: Connection timeout in seconds (default: 60)
    DATABASE_URL: PostgreSQL connection string
    REDIS_URL: Redis connection string
    MINIO_ENDPOINT: MinIO/S3 endpoint
    MINIO_ROOT_USER: MinIO access key
    MINIO_ROOT_PASSWORD: MinIO secret key
    MINIO_BUCKET: S3 bucket name

SSOT Reference: spec 006-smtp-ingest, §3.3 (SMTP Ingest)
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from aiosmtpd.controller import Controller
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add backend/src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from infrastructure.ingest.smtp_handler import OrderFlowSMTPHandler
from infrastructure.storage.s3_storage_adapter import S3StorageAdapter
from workers.attachment_extraction_worker import enqueue_attachment_extraction

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def get_env(key: str, default: str = None) -> str:
    """Get environment variable with optional default."""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


async def main():
    """Start SMTP server with OrderFlow handler."""
    # Load configuration from environment
    smtp_host = get_env('SMTP_HOST', '0.0.0.0')
    smtp_port = int(get_env('SMTP_PORT', '25'))
    smtp_domain = get_env('SMTP_DOMAIN', 'orderflow.example.com')
    max_message_size = int(get_env('SMTP_MAX_MESSAGE_SIZE', '26214400'))
    max_connections = int(get_env('SMTP_MAX_CONNECTIONS', '100'))
    connection_timeout = int(get_env('SMTP_CONNECTION_TIMEOUT', '60'))

    database_url = get_env('DATABASE_URL')

    # MinIO/S3 configuration
    minio_endpoint = get_env('MINIO_ENDPOINT')
    minio_user = get_env('MINIO_ROOT_USER')
    minio_password = get_env('MINIO_ROOT_PASSWORD')
    minio_bucket = get_env('MINIO_BUCKET', 'orderflow-documents')
    minio_use_ssl = get_env('MINIO_USE_SSL', 'false').lower() == 'true'

    logger.info("=== OrderFlow SMTP Server Starting ===")
    logger.info(f"SMTP Bind: {smtp_host}:{smtp_port}")
    logger.info(f"SMTP Domain: {smtp_domain}")
    logger.info(f"Max Message Size: {max_message_size} bytes")
    logger.info(f"Max Connections: {max_connections}")
    logger.info(f"Connection Timeout: {connection_timeout}s")
    logger.info(f"Database: {database_url.split('@')[-1]}")  # Hide credentials
    logger.info(f"Storage: {minio_endpoint}/{minio_bucket}")

    # Create async database engine
    # Convert sync DATABASE_URL to async (postgresql:// -> postgresql+asyncpg://)
    async_database_url = database_url.replace(
        'postgresql://',
        'postgresql+asyncpg://'
    )

    engine = create_async_engine(
        async_database_url,
        pool_pre_ping=True,
        echo=False,
    )

    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    @asynccontextmanager
    async def get_db_session():
        """Async context manager for database sessions."""
        async with async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    # Create storage adapter
    storage_adapter = S3StorageAdapter(
        endpoint_url=f"http://{minio_endpoint}" if not minio_use_ssl else f"https://{minio_endpoint}",
        access_key=minio_user,
        secret_key=minio_password,
        bucket_name=minio_bucket,
        region='us-east-1',
    )

    logger.info("Storage adapter initialized")

    # Create SMTP handler
    smtp_handler = OrderFlowSMTPHandler(
        get_db_session=get_db_session,
        storage_adapter=storage_adapter,
        enqueue_extraction_job=enqueue_attachment_extraction,
        max_connections=max_connections,
        connection_timeout=connection_timeout,
        rate_limit_per_ip=None,  # Disabled by default, can be enabled via env var
    )

    logger.info("SMTP handler initialized")

    # Create and start SMTP controller
    # Note: aiosmtpd Controller does not directly support max_connections or timeout
    # These are handled at the asyncio server level via ready_timeout parameter
    # For production deployments, use a reverse proxy (nginx) for connection limiting
    controller = Controller(
        smtp_handler,
        hostname=smtp_host,
        port=smtp_port,
        server_hostname=smtp_domain,
        # Enable SMTPUTF8 for international email addresses
        enable_SMTPUTF8=True,
        # Timeout for completing the connection handshake
        ready_timeout=connection_timeout,
    )

    controller.start()

    logger.info(f"SMTP server started on {smtp_host}:{smtp_port}")
    logger.info(f"Accepting emails to: orders+<org_slug>@{smtp_domain}")
    logger.info("Press Ctrl+C to stop")

    try:
        # Keep server running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour, wake up to handle signals
    except KeyboardInterrupt:
        logger.info("Shutting down SMTP server...")
        controller.stop()
        logger.info("SMTP server stopped")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, exiting")
        sys.exit(0)
    except Exception as e:
        logger.error(f"SMTP server failed: {e}", exc_info=True)
        sys.exit(1)
