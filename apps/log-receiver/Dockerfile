# KillKrill Log Receiver Dockerfile
# High-performance log ingestion with XDP support

FROM python:3.12-slim AS builder

# Install build dependencies including XDP/eBPF tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    libbpf-dev \
    libelf-dev \
    linux-headers-generic \
    clang \
    llvm \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

FROM python:3.12-slim AS runtime

# Install runtime dependencies for XDP and networking
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    iproute2 \
    iptables \
    libbpf1 \
    libelf1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Create app user and directory
RUN useradd -m -u 1000 killkrill
WORKDIR /app

# Copy application code
COPY apps/log-receiver/ /app/
COPY shared/ /app/shared/

# Set ownership
RUN chown -R killkrill:killkrill /app

# XDP requires privileged access, but we'll drop privileges where possible
# The container will run with NET_ADMIN and SYS_ADMIN capabilities

# Add Python packages to PATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8081/healthz || exit 1

# Expose ports
EXPOSE 8081
EXPOSE 10000-11000/udp

# Start application (will run as root due to XDP requirements)
CMD ["python", "app.py"]