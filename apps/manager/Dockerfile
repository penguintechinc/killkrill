# KillKrill Manager Dockerfile
# Python venv build for reliability

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY apps/manager/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.12-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create app user and directory
RUN useradd -m -u 1000 killkrill
WORKDIR /app

# Copy application code
COPY apps/manager/ /app/
COPY shared/ /app/shared/

# Set ownership
RUN chown -R killkrill:killkrill /app

# Switch to non-root user
USER killkrill

# Use virtual environment
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Expose port
EXPOSE 8080

# Start application with py4web
CMD ["py4web", "run", ".", "--host", "0.0.0.0", "--port", "8080", "--password_file", "password.txt"]