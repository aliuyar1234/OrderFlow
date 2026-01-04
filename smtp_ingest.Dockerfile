# SMTP Ingest Server Dockerfile for OrderFlow
# Runs dedicated SMTP server for receiving order emails

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements/base.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install async database driver
RUN pip install --no-cache-dir asyncpg

# Copy backend source
COPY backend/src /app/src
COPY backend/scripts /app/scripts

# Make startup script executable
RUN chmod +x /app/scripts/start_smtp_server.py

# Expose SMTP port
EXPOSE 25

# Health check (TCP port check)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 25)); s.close()" || exit 1

# Run SMTP server
CMD ["python", "/app/scripts/start_smtp_server.py"]
