# =============================================================================
# OrderFlow Backend Dockerfile
# Multi-stage build for production deployment
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# Installs dependencies and creates virtual environment
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
WORKDIR /app
COPY backend/requirements/base.txt requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production Runtime
# Minimal image with only runtime dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Labels for container metadata
LABEL org.opencontainers.image.title="OrderFlow API" \
      org.opencontainers.image.description="B2B Order Automation Platform" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="OrderFlow"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    # Application settings
    ENV=production \
    DEBUG=false \
    LOG_LEVEL=INFO \
    LOG_JSON=true \
    # Server settings
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=4 \
    # Path settings
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    curl \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 orderflow && \
    useradd --uid 1000 --gid orderflow --shell /bin/bash --create-home orderflow

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=orderflow:orderflow backend/src ./src
COPY --chown=orderflow:orderflow backend/migrations ./migrations
COPY --chown=orderflow:orderflow backend/alembic.ini ./alembic.ini

# Create necessary directories
RUN mkdir -p /app/logs /app/tmp && \
    chown -R orderflow:orderflow /app

# Switch to non-root user
USER orderflow

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]

# -----------------------------------------------------------------------------
# Stage 3: Development (optional, for local development)
# -----------------------------------------------------------------------------
FROM runtime AS development

# Switch to root for dev dependencies
USER root

# Install dev dependencies
COPY backend/requirements/dev.txt /tmp/dev-requirements.txt
RUN pip install -r /tmp/dev-requirements.txt && rm /tmp/dev-requirements.txt

# Install development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Switch back to non-root user
USER orderflow

# Override command for development with hot reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
