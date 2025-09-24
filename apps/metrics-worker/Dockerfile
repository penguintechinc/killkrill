# KillKrill Metrics Worker Dockerfile
# Redis Streams consumer for Prometheus integration

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

FROM python:3.12-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Create app user and directory
RUN useradd -m -u 1000 killkrill
WORKDIR /app

# Copy application code
COPY apps/metrics-worker/ /app/
COPY shared/ /app/shared/

# Set ownership
RUN chown -R killkrill:killkrill /app

# Switch to non-root user
USER killkrill

# Add Python packages to PATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Health check (check if main process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ps aux | grep -v grep | grep "python app.py" || exit 1

# Start application
CMD ["python", "app.py"]