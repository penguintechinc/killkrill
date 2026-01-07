# Killkrill Development Standards

Development and operational standards for the Killkrill data processing system.

## Code Quality Standards

### Go Services (API, K8s Operator, K8s Agent)

**Minimum Requirements**:
- Go 1.23.5 or later
- Pass `go vet ./...` without warnings
- Pass `staticcheck` (https://staticcheck.dev/)
- Pass `gosec` security scanning
- Minimum 80% code coverage (unit tests)
- `gofmt` code formatting
- No hardcoded secrets or credentials

**Linting Tools**:
```bash
golangci-lint run ./...
gosec ./...
go vet ./...
staticcheck ./...
```

**Code Style**:
- Follow Go idioms from "Effective Go"
- Use interfaces for abstractions
- Minimize exported surface area
- Comprehensive error handling
- Context usage for cancellation

**Performance Requirements**:
- API: Handle 10K+ req/sec
- Workers: Process 100K+ events/sec
- Operators: Sub-second reconciliation time
- Memory: <500MB per service
- CPU: Efficient concurrency via goroutines

### Python Services (Workers, Receivers, Manager)

**Minimum Requirements**:
- Python 3.12 minimum
- Pass `flake8` linting
- Pass `black` formatting check
- Pass `isort` import sorting
- Pass `mypy` type checking (best effort)
- Pass `bandit` security scanning
- Minimum 80% code coverage (unit tests)
- PEP 8, PEP 257, PEP 484 compliance

**Linting Tools**:
```bash
black . --check
isort . --check-only
flake8 .
mypy . --ignore-missing-imports
bandit -r . --skip B101,B601
```

**Code Style**:
- Type hints for all functions (PEP 484)
- Docstrings for all modules/classes/functions (PEP 257)
- Use dataclasses with slots for memory efficiency
- Comprehensive error handling
- Logging at appropriate levels

**Performance Requirements**:
- Workers: Process 50K+ events/sec
- Receivers: Ingest 100K+ msg/sec with Quart + Hypercorn
- Memory: <500MB per service
- Response time: <100ms for async operations
- Async/await for I/O operations (Quart mandatory for all web services)

**Quart Framework Requirements**:
- Use Quart for all new Python web services
- Hypercorn ASGI server for production deployments
- Blueprint organization for modular routes
- Async route handlers: `async def route_handler()`
- PyDAL for database operations with async context
- Structured logging with structlog
- JWT or custom auth decorators for protected endpoints

### Testing Standards

**Unit Tests**:
- Isolated from external dependencies
- No network access required
- Mock all I/O operations and async calls
- Fast execution (<1ms per test)
- Test both success and failure paths
- Coverage target: 80% minimum
- Use pytest with async fixtures for Quart apps

**Integration Tests**:
- Test component interactions with Docker containers
- Real database/cache usage OK
- Test Quart blueprints and async handlers
- Should complete in <30 seconds total
- Test error conditions and auth decorators

**End-to-End Tests**:
- Full system workflows with production config
- Production-like environment (docker-compose.yml)
- Real data scenarios through message queues
- Performance baseline validation

**Pytest Command Reference**:
```bash
make test                    # Run all tests (unit + integration + e2e)
make test-unit              # Unit tests only (fast)
make test-integration       # Integration tests with Docker
make test-e2e               # End-to-end workflow tests
pytest tests/unit -v        # Verbose unit test output
pytest tests/integration --durations=10  # Show 10 slowest tests
```

---

## CI/CD Standards

### Workflow Configuration

All workflows must follow these standards:

#### Path Filters

```yaml
on:
  push:
    paths:
      - '.version'                    # Always monitored
      - 'go.mod'                      # Go dependency changes
      - '**/*.go'                     # All Go source
      - 'apps/**'                     # All service code
      - 'requirements.txt'            # Python dependencies
      - '**/*.py'                     # All Python source
      - 'package.json'                # Node.js dependencies
      - 'Dockerfile*'                 # Container definitions
      - '.github/workflows/.*'        # Workflow changes
```

#### Version Detection

Every workflow must detect version:

```yaml
- name: Detect version
  id: version
  run: |
    if [ -f .version ]; then
      VERSION=$(cat .version | tr -d '[:space:]')
      echo "version=${VERSION}" >> $GITHUB_OUTPUT
    else
      echo "version=0.0.0" >> $GITHUB_OUTPUT
    fi
```

#### Epoch64 Timestamp

All builds must generate timestamp:

```yaml
- name: Generate epoch64 timestamp
  id: timestamp
  run: |
    EPOCH64=$(date +%s%N | cut -b1-13)
    echo "epoch64=${EPOCH64}" >> $GITHUB_OUTPUT
```

#### Concurrency Control

Prevent duplicate runs:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### Security Scanning Requirements

#### Go Security (gosec)

**Required for**: api, k8s-operator, k8s-agent

```bash
gosec ./... -fmt json -out gosec-results.json
```

**Must Pass**:
- No high-severity findings (fixable)
- Low-severity findings documented

#### Python Security (bandit)

**Required for**: log-worker, metrics-worker, log-receiver, metrics-receiver, manager

```bash
bandit -r . -f json -o bandit-results.json --skip B101,B601
```

**Must Pass**:
- No high-severity findings (fixable)
- Excluded: B101 (assert), B601 (paramiko)

#### Container Security (Trivy)

**Scans**: All built container images

```bash
trivy image ghcr.io/killkrill/api:latest
```

**Policy**:
- HIGH and CRITICAL vulnerabilities: Must be fixed
- MEDIUM vulnerabilities: Should be addressed
- LOW vulnerabilities: Monitor, fix when convenient

### Build Standards

#### Multi-Architecture Support

All containers must support:
- `linux/amd64` (x86-64)
- `linux/arm64` (ARM64/Apple Silicon)

```yaml
platforms: linux/amd64,linux/arm64
```

#### Base Images

Use **Debian-slim** for production:

```dockerfile
FROM debian:stable-slim
# or
FROM golang:1.23-slim
FROM python:3.12-slim
```

**Rationale**:
- Smaller than full Debian
- More compatible than Alpine
- Reduced CVE surface vs. full OS images

#### Dockerfile Standards

- Multi-stage builds for optimization
- Minimal runtime image
- Non-root user for execution
- Explicit HEALTHCHECK
- Build args for version/metadata

```dockerfile
FROM golang:1.23-slim AS builder
WORKDIR /app
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o app

FROM debian:stable-slim
RUN useradd -u 1000 app
COPY --from=builder /app /app
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8080/health
CMD ["/app"]
```

#### Image Tagging

**Version Tag Format**:

| Scenario | Branch | Tag |
|----------|--------|-----|
| Regular commit | main | `main-<EPOCH64>-<DATE>` |
| Version update | main | `v<VERSION>-beta` |
| Release | tag | `v<VERSION>` + `latest` |
| Regular commit | develop | `develop-<EPOCH64>-<DATE>` |
| Version update | develop | `v<VERSION>-alpha` |

#### Metadata Labels

All images must include:

```dockerfile
LABEL org.opencontainers.image.version="1.2.3"
LABEL org.opencontainers.image.created="2025-01-15T10:30:00Z"
LABEL org.opencontainers.image.revision="abc123def456"
LABEL org.opencontainers.image.source="https://github.com/..."
LABEL org.opencontainers.image.title="killkrill-api"
LABEL org.opencontainers.image.description="Killkrill API service"
```

---

## Service Architecture Standards

### API Service (Go)

**Purpose**: Main entry point for all data submission and queries

**Requirements**:
- REST API with versioning: `/api/v1/...`
- Health check: `GET /health`
- Metrics endpoint: `GET /metrics` (Prometheus format)
- Rate limiting
- Request validation
- Error handling with proper HTTP status codes
- Structured logging with correlation IDs
- License validation for enterprise features

**Performance SLA**:
- P50: <5ms
- P95: <20ms
- P99: <100ms
- Throughput: 10K req/sec minimum

### Worker Services (Python)

**Components**:
- log-worker: Processes log entries
- metrics-worker: Processes metrics and aggregations

**Requirements**:
- Consume from message queue (Redis/Kafka)
- Idempotent processing
- Batch operations for efficiency
- Dead-letter queue handling
- Circuit breaker for failures
- Structured logging
- Metrics emission

**Performance SLA**:
- Latency: <1 second per event
- Throughput: 50K events/sec minimum
- Memory: <500MB

### Receiver Services (Python)

**Components**:
- log-receiver: Syslog/HTTP ingestion
- metrics-receiver: Prometheus/HTTP ingestion

**Requirements**:
- Accept multiple formats (syslog, HTTP, gRPC)
- High-throughput ingestion
- Connection pooling
- Buffer management
- Graceful degradation under load
- Health checks for upstream dependencies

**Performance SLA**:
- Latency: <100ms for submission
- Throughput: 100K msg/sec minimum
- Tail latencies: <500ms at P99

### Manager Service (Python)

**Purpose**: Configuration, monitoring, and administration

**Requirements**:
- Web UI for management
- REST API for automation
- Database connectivity
- User authentication
- Role-based access control
- Audit logging
- Integration with other services

### K8s Operator (Go)

**Purpose**: Kubernetes-native management of Killkrill deployments

**Requirements**:
- Watch Custom Resources
- Reconcile service deployments
- Handle scale-up/scale-down
- Monitor pod health
- Update service configurations
- Emit events for user awareness

**Controller Patterns**:
- Exponential backoff for retries
- Status subresource updates
- Finalizers for cleanup
- Owner references for garbage collection

### K8s Agent (Go)

**Purpose**: Per-pod agent for data collection and coordination

**Requirements**:
- Sidecar container model
- Pod-local metrics/logs collection
- Communication with API
- Minimal resource overhead (<50MB)
- Auto-discovery of other pods
- Health endpoint for kubelet probes

---

## Kubernetes Deployment Standards

### Deployment Manifests

All services must provide:
- Deployment with resource requests/limits
- Service for internal/external access
- ConfigMap for configuration
- Secret for credentials
- Horizontal Pod Autoscaler (HPA)
- Pod Disruption Budget
- Network Policy

### Resource Requirements

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| api | 250m | 1000m | 256Mi | 512Mi |
| log-worker | 200m | 800m | 256Mi | 512Mi |
| metrics-worker | 200m | 800m | 256Mi | 512Mi |
| log-receiver | 250m | 1000m | 256Mi | 512Mi |
| metrics-receiver | 250m | 1000m | 256Mi | 512Mi |
| manager | 200m | 500m | 256Mi | 512Mi |
| k8s-operator | 100m | 500m | 128Mi | 256Mi |
| k8s-agent | 50m | 200m | 64Mi | 128Mi |

### Health Checks

**Liveness Probe**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

**Readiness Probe**:
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

### Logging

All services must emit structured JSON logs to stdout:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "INFO",
  "service": "api",
  "correlation_id": "req-12345",
  "message": "Request processed",
  "duration_ms": 45,
  "status": 200
}
```

### Monitoring

All services must expose Prometheus metrics:

```
http_requests_total{method="POST",endpoint="/api/v1/logs",status="200"} 1250
http_request_duration_seconds_bucket{le="0.01",method="POST"} 450
```

---

## Version Management

### .version File Format

```
1.2.3
```

**Format**: Semantic versioning only (major.minor.patch)

**Process**:
1. Update `.version` file on main branch
2. Commit and push
3. `version-release.yml` creates pre-release
4. Tag release with `vX.X.X`
5. `release.yml` publishes production images

**Example**:
```bash
echo "1.2.3" > .version
git add .version
git commit -m "Release v1.2.3"
git push origin main
# Auto-creates GitHub pre-release
# Tag creates final release with production images
```

---

## Security Standards

### Container Security

- Scan all images with Trivy before deployment
- Use minimal base images (Debian-slim)
- Run as non-root user (UID 1000+)
- Use read-only root filesystem where possible
- Disable privileged mode
- Drop unsafe Linux capabilities

### Secret Management

- Never commit secrets to repository
- Use GitHub Secrets for CI/CD
- Use Kubernetes Secrets at runtime
- Rotate secrets regularly
- Audit secret access
- Use RBAC to limit secret access

### Network Security

- Use TLS for all external communication
- Implement mTLS for service-to-service
- Use Network Policies in Kubernetes
- Restrict ingress to necessary ports
- Use service mesh (Istio) for advanced policies

---

## Checklist for New Service

When adding a new service to Killkrill:

- [ ] Create service directory in `apps/`
- [ ] Implement health check endpoint: `GET /health`
- [ ] Implement metrics endpoint: `GET /metrics` (if applicable)
- [ ] Create Dockerfile with Debian-slim base
- [ ] Add unit tests (80%+ coverage target)
- [ ] Add linting to CI pipeline (gosec/bandit)
- [ ] Create Kubernetes manifests in `k8s/`
- [ ] Document in README and WORKFLOWS.md
- [ ] Configure resource requests/limits
- [ ] Set up health probes
- [ ] Implement structured logging
- [ ] Add to service matrix in workflows

---

## Reference Documents

- [WORKFLOWS.md](./WORKFLOWS.md) - CI/CD pipeline documentation
- [API.md](./api.md) - API specification
- [DEPLOYMENT.md](./deployment.md) - Deployment procedures
- [ARCHITECTURE.md](./architecture.md) - System architecture
