"""Application configuration via environment variables.

Provides type-safe settings loading using pydantic-settings.
Environment variables can be loaded from a .env file.

SSOT Reference: §11 (Environment Configuration)
"""

import os
from typing import Optional
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # Fallback for older pydantic


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings have sensible defaults for development.
    Production deployments MUST set security-critical values.

    Environment Variables:
        DATABASE_URL: PostgreSQL connection string
        REDIS_URL: Redis connection string (Celery broker)
        SECRET_KEY: JWT signing key (MUST be set in production)
        PASSWORD_PEPPER: Password hashing pepper (MUST be set in production)
        S3_ENDPOINT_URL: S3-compatible endpoint (MinIO in dev)
        S3_ACCESS_KEY_ID: S3 access key
        S3_SECRET_ACCESS_KEY: S3 secret key
        S3_BUCKET_NAME: Default bucket for file storage
        OPENAI_API_KEY: OpenAI API key for embeddings/LLM
        ANTHROPIC_API_KEY: Anthropic API key for Claude
        DEBUG: Enable debug mode (default False)
        LOG_LEVEL: Logging level (default INFO)
    """

    # Database
    DATABASE_URL: str = "postgresql://orderflow:dev_password@localhost:5432/orderflow"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "dev-secret-key-CHANGE-IN-PRODUCTION"
    PASSWORD_PEPPER: str = "dev-pepper-key-CHANGE-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Object Storage (S3/MinIO)
    S3_ENDPOINT_URL: Optional[str] = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "orderflow-documents"
    S3_REGION: str = "us-east-1"

    # AI Providers
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Application
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # Email (SMTP ingest)
    SMTP_HOST: str = "0.0.0.0"
    SMTP_PORT: int = 2525
    SMTP_MAX_SIZE: int = 26_214_400  # 25 MB

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache for singleton behavior.
    Call get_settings.cache_clear() to reload settings.
    """
    return Settings()


# Module-level settings instance
settings = get_settings()
