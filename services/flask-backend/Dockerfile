# Multi-stage build for KillKrill Flask Backend
# Supports both Flask HTTP (port 5000) and gRPC (port 50051)

# Stage 1: Builder
FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY services/flask-backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r backend && useradd -r -g backend backend

# Copy Python packages from builder
COPY --from=builder --chown=backend:backend /root/.local /home/backend/.local

# Copy application code
COPY --chown=backend:backend services/flask-backend/ .
COPY --chown=backend:backend shared/ /app/shared/

# Set environment variables
ENV PATH=/home/backend/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    FLASK_ENV=production \
    FLASK_PORT=5000 \
    GRPC_PORT=50051

# Switch to non-root user
USER backend

# Expose ports
EXPOSE 5000 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/healthz || exit 1

# Start application
CMD ["/app/start.sh"]
