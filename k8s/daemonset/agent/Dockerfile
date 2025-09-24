# Build stage
FROM golang:1.23-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata gcc musl-dev linux-headers

# Set working directory
WORKDIR /src

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build args for version info
ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown

# Build the binary
RUN CGO_ENABLED=1 GOOS=linux go build \
    -ldflags="-w -s -X main.Version=${VERSION} -X main.GitCommit=${GIT_COMMIT} -X main.BuildTime=${BUILD_TIME}" \
    -a -installsuffix cgo \
    -o killkrill-agent \
    ./cmd/agent

# Runtime stage
FROM alpine:3.19

# Install runtime dependencies
RUN apk add --no-cache \
    ca-certificates \
    tzdata \
    curl \
    && rm -rf /var/cache/apk/*

# Create non-root user (but we'll run as root for privileged access)
RUN addgroup -g 1000 killkrill && \
    adduser -D -u 1000 -G killkrill killkrill

# Create directories
RUN mkdir -p /etc/killkrill /var/lib/killkrill /var/log/killkrill && \
    chown -R killkrill:killkrill /etc/killkrill /var/lib/killkrill /var/log/killkrill

# Copy binary from builder
COPY --from=builder /src/killkrill-agent /usr/local/bin/killkrill-agent

# Copy default configuration
COPY --from=builder /src/config/default.yaml /etc/killkrill/config.yaml

# Set permissions
RUN chmod +x /usr/local/bin/killkrill-agent

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Expose ports
EXPOSE 8080 8443

# Set environment variables
ENV CONFIG_FILE=/etc/killkrill/config.yaml
ENV LOG_LEVEL=info
ENV LOG_FORMAT=json

# Labels
LABEL org.opencontainers.image.title="KillKrill Agent"
LABEL org.opencontainers.image.description="Kubernetes log and metrics collection agent for KillKrill platform"
LABEL org.opencontainers.image.vendor="Penguin Tech Inc"
LABEL org.opencontainers.image.licenses="Limited AGPL3"
LABEL org.opencontainers.image.source="https://github.com/penguintechinc/killkrill"

# Run as root for privileged access to node resources
USER root

# Set working directory
WORKDIR /

# Command
ENTRYPOINT ["/usr/local/bin/killkrill-agent"]