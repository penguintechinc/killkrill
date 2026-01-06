# KillKrill Pre-Commit Checklist

**CRITICAL: This checklist MUST be followed before every commit to ensure code quality, security, and functionality for log/metrics workers.**

## Automated Pre-Commit Script

**Run the automated pre-commit script to execute all checks:**

```bash
./scripts/pre-commit/pre-commit.sh
```

This script will:
1. Run all checks in the correct order
2. Log output to `/tmp/pre-commit-killkrill-<epoch>.log`
3. Provide a summary of pass/fail status
4. Echo the log file location for review

**Individual check scripts** (run separately if needed):
- `./scripts/pre-commit/check-python.sh` - Python linting & security (workers, receivers, manager)
- `./scripts/pre-commit/check-go.sh` - Go linting & security (API, K8s components)
- `./scripts/pre-commit/check-node.sh` - Node.js/React linting, audit & build (Manager UI)
- `./scripts/pre-commit/check-security.sh` - All security scans
- `./scripts/pre-commit/check-secrets.sh` - Secret detection
- `./scripts/pre-commit/check-docker.sh` - Docker build & validation
- `./scripts/pre-commit/check-tests.sh` - Unit and integration tests

## Required Steps (In Order)

Before committing, run in this order (or use `./scripts/pre-commit/pre-commit.sh`):

### Foundation Checks
- [ ] **Linters**:
  - `flake8 services/log-worker services/metrics-worker services/log-receiver services/metrics-receiver services/manager` (Python)
  - `npm run lint` (Node.js - Manager UI)
  - `golangci-lint run` (Go - API, K8s components)
- [ ] **Security scans**:
  - `bandit -r services/log-worker services/metrics-worker services/log-receiver services/metrics-receiver services/manager` (Python)
  - `npm audit` (Node.js - Manager UI)
  - `gosec ./apps/api ./apps/k8s-operator ./apps/k8s-agent` (Go)
- [ ] **No secrets**: Verify no credentials, API keys, or tokens in code

### Build & Integration Verification
- [ ] **Build & Run**: Verify code compiles and containers start successfully
- [ ] **Smoke tests** (mandatory, <2 min): `make smoke-test`
  - All containers build without errors (log-worker, metrics-worker, receivers, manager)
  - All containers start and remain healthy
  - Log and metrics receiver health endpoints respond with 200 status
  - Redis Streams connectivity verified
  - Elasticsearch and Prometheus backends respond
  - See: [Testing Documentation - Smoke Tests](TESTING.md#smoke-tests)

### Feature Testing & Worker Validation
- [ ] **Mock data** (for testing workers): Ensure 3-4 test items per worker via `make seed-mock-data`
  - Populate Redis Streams with realistic log and metrics entries
  - Needed before testing worker processing and output
  - See: [Testing Documentation - Mock Data Scripts](TESTING.md#mock-data-scripts)
- [ ] **Worker output verification**:
  - Log worker: Verify logs appear in Elasticsearch indices
  - Metrics worker: Verify metrics appear in Prometheus targets
  - Check worker logs for errors or warnings

### Comprehensive Testing
- [ ] **Unit tests**: `pytest tests/unit/`
  - Log/metrics parsing tests must pass
  - Worker transformation tests must pass
  - Receiver authentication tests must pass
  - Network isolated, mocked dependencies
  - Must pass before committing
- [ ] **Integration tests**: `pytest tests/integration/`
  - Log worker → Elasticsearch pipeline tests
  - Metrics worker → Prometheus pipeline tests
  - Redis Streams consumer group tests
  - See: [Testing Documentation - Integration Tests](TESTING.md#integration-tests)

### Multi-Service Testing
- [ ] **Receiver protocol testing**:
  - [ ] HTTP REST API: `curl -X POST http://localhost:8081/api/v1/logs ...`
  - [ ] Syslog UDP: `echo "<14>message" | nc -u localhost 514`
  - [ ] Prometheus metrics: `curl -X POST http://localhost:8082/api/v1/metrics ...`
  - See: [Testing Documentation - Multi-Protocol Testing](TESTING.md#multi-protocol-testing)
- [ ] **Queue testing**: Verify Redis Streams consumer group processing
  - `redis-cli XINFO GROUPS logs-stream`
  - Verify message acknowledgment (XPENDING output)
  - Verify no message loss on worker restart

### Worker-Specific Validation
- [ ] **Log worker modifications** (if changed):
  - [ ] Log parsing handles all expected formats (JSON, structured, unstructured)
  - [ ] Field extraction works for all configured log sources
  - [ ] Transformation rules apply correctly
  - [ ] Error handling for malformed logs
  - [ ] Performance: processes >1000 logs/sec from queue
- [ ] **Metrics worker modifications** (if changed):
  - [ ] Metrics parsing handles Prometheus format
  - [ ] Histogram/counter/gauge aggregation works correctly
  - [ ] Label extraction and normalization works
  - [ ] Output format compatible with Prometheus scrape
  - [ ] Performance: processes >1000 metrics/sec from queue
- [ ] **Receiver modifications** (if changed):
  - [ ] Authentication/authorization works (API key, JWT)
  - [ ] Rate limiting enforced
  - [ ] Messages queued to Redis Streams correctly
  - [ ] Error responses appropriate (400, 401, 429, etc.)

### Finalization
- [ ] **Version updates**: Update `.version` if releasing new version
- [ ] **Documentation**: Update docs if adding/changing workflows or worker behavior
- [ ] **Docker builds**: Verify Dockerfile uses debian-slim base (no alpine)
- [ ] **Cross-architecture**: (Optional) Test alternate architecture with QEMU
  - `docker buildx build --platform linux/arm64 services/log-worker/` (if on amd64)
  - `docker buildx build --platform linux/amd64 services/log-worker/` (if on arm64)
  - See: [Testing Documentation - Cross-Architecture Testing](TESTING.md#cross-architecture-testing)

## Language-Specific Commands

### Python (Log/Metrics Workers, Receivers, Manager)

```bash
# Linting
flake8 services/log-worker services/metrics-worker services/log-receiver services/metrics-receiver services/manager
black --check services/
isort --check services/
mypy services/

# Security
bandit -r services/log-worker services/metrics-worker services/log-receiver services/metrics-receiver services/manager
safety check

# Build & Run
python -m py_compile services/log-worker/*.py          # Syntax check
pip install -r services/log-worker/requirements.txt   # Dependencies
python services/log-worker/main.py &                  # Verify it starts (then kill)

# Tests
pytest tests/unit/
pytest tests/integration/
```

### Go (API, K8s Operator, K8s Agent)

```bash
# Linting
golangci-lint run ./apps/api ./apps/k8s-operator ./apps/k8s-agent

# Security
gosec ./apps/api ./apps/k8s-operator ./apps/k8s-agent

# Build & Run
go build ./apps/api/...                   # Compile all packages
go run ./apps/api/main.go &               # Verify it starts (then kill)

# Tests
go test ./apps/api/...
go test ./apps/k8s-operator/...
```

### Node.js / JavaScript / TypeScript / React (Manager UI)

```bash
# Linting
npm run lint
# or
npx eslint services/manager/

# Security (REQUIRED)
npm audit                          # Check for vulnerabilities
npm audit fix                      # Auto-fix if possible

# Build & Run
npm run build                      # Compile/bundle
npm start &                        # Verify it starts (then kill)

# Tests
npm test
```

### Docker / Containers

```bash
# Lint Dockerfiles
hadolint Dockerfile
hadolint services/*/Dockerfile

# Verify base image (debian-slim, NOT alpine)
grep -E "^FROM.*slim" services/*/Dockerfile

# Build & Run
docker build -t log-worker:test services/log-worker/     # Build image
docker run -d --name test-container log-worker:test      # Start container
docker logs test-container                               # Check for errors
docker stop test-container && docker rm test-container   # Cleanup

# Docker Compose (if applicable)
docker compose -f docker-compose.dev.yml build           # Build all services
docker compose -f docker-compose.dev.yml up -d           # Start all services
docker compose -f docker-compose.dev.yml logs            # Check for errors
docker compose -f docker-compose.dev.yml down            # Cleanup
```

## Commit Rules

- **NEVER commit automatically** unless explicitly requested by the user
- **NEVER push to remote repositories** under any circumstances
- **ONLY commit when explicitly asked** - never assume commit permission
- **Wait for approval** before running `git commit`

## Security Scanning Requirements

### Before Every Commit
- **Run security audits on all modified packages**:
  - **Go packages**: Run `gosec ./apps/api ./apps/k8s-operator ./apps/k8s-agent` on modified Go services
  - **Node.js packages**: Run `npm audit` on modified Node.js services (Manager UI)
  - **Python packages**: Run `bandit -r services/` and `safety check` on modified Python services (workers, receivers)
- **Do NOT commit if security vulnerabilities are found** - fix all issues first
- **Document vulnerability fixes** in commit message if applicable

### Vulnerability Response
1. Identify affected packages and severity
2. Update to patched versions immediately
3. Test updated dependencies thoroughly
4. Document security fixes in commit messages
5. Verify no new vulnerabilities introduced

## API Testing Requirements

Before committing changes to receiver or API services:

- **Create and run API testing scripts** for each modified service
- **Testing scope**: All new endpoints and modified functionality
- **Test files location**: `tests/api/` directory with service-specific subdirectories
  - `tests/api/log-receiver/` - Log receiver API tests
  - `tests/api/metrics-receiver/` - Metrics receiver API tests
  - `tests/api/api/` - Go API service tests
  - `tests/api/manager/` - Manager service API tests
- **Run before commit**: Each test script should be executable and pass completely
- **Test coverage**: Health checks, authentication, CRUD operations, error cases

### Example Receiver API Test

```bash
#!/bin/bash
# tests/api/log-receiver/test-endpoints.sh

set -e

API_URL="http://localhost:8081"
AUTH_TOKEN="PENG-DEMO-DEMO-DEMO-DEMO-DEMO"

echo "Testing log-receiver endpoints..."

# Test health endpoint
curl -s "$API_URL/healthz" | grep -q "healthy" && echo "✓ Health check OK"

# Test API authentication
curl -s -X POST "$API_URL/api/v1/logs" \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2024-01-06T12:00:00Z","service":"test","level":"info","message":"test"}' | \
  grep -q "401" && echo "✓ Requires authentication"

# Test with auth token
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$API_URL/api/v1/logs" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2024-01-06T12:00:00Z","service":"test","level":"info","message":"test"}')

[ "$HTTP_CODE" = "202" ] && echo "✓ Accepts authenticated requests" || exit 1
```

## Worker Testing Requirements

### Log Worker
Before committing log worker changes:

- [ ] **Parse tests**: All log formats parse correctly
  - [ ] JSON format with all fields
  - [ ] Missing optional fields handled
  - [ ] Invalid timestamps rejected
  - [ ] Invalid log levels handled
- [ ] **Integration test**:
  - [ ] Consumes from Redis Streams
  - [ ] Outputs to Elasticsearch with proper indexing
  - [ ] Acknowledges messages correctly
  - [ ] Handles batch processing (100+ logs)
- [ ] **Error handling**:
  - [ ] Malformed logs don't crash worker
  - [ ] Elasticsearch failures are retried
  - [ ] Worker recovers from transient errors

### Metrics Worker
Before committing metrics worker changes:

- [ ] **Parse tests**: Prometheus format parsing
  - [ ] Counter metrics recognized
  - [ ] Histogram metrics aggregated
  - [ ] Gauge metrics extracted
  - [ ] Labels normalized
- [ ] **Integration test**:
  - [ ] Consumes from Redis Streams
  - [ ] Outputs to Prometheus-compatible format
  - [ ] Timestamp handling correct
  - [ ] Batch processing works (100+ metrics)
- [ ] **Error handling**:
  - [ ] Invalid metric formats skipped with logging
  - [ ] Prometheus output failures are retried
  - [ ] Worker maintains state across restarts

## Receiver Testing Requirements

### Log Receiver
Before committing log receiver changes:

- [ ] **Authentication test**: API key, JWT token validation
- [ ] **Protocol test**: HTTP/REST API working
- [ ] **Syslog test**: UDP Syslog reception (RFC3164 and RFC5424)
- [ ] **Rate limiting**: Enforced appropriately
- [ ] **Error responses**: Proper HTTP status codes
  - [ ] 202 for successful submissions
  - [ ] 400 for malformed payloads
  - [ ] 401 for auth failures
  - [ ] 429 for rate limit exceeded

### Metrics Receiver
Before committing metrics receiver changes:

- [ ] **Authentication test**: API key, JWT token validation
- [ ] **Protocol test**: HTTP/REST API working
- [ ] **Prometheus format**: Accepts Prometheus-compatible format
- [ ] **Rate limiting**: Enforced appropriately
- [ ] **Labeling**: Metric labels preserved/normalized

## Queue Processing Requirements

Before committing any worker or receiver changes:

- [ ] **Redis Streams connectivity**: `redis-cli XLEN <stream-name>`
- [ ] **Consumer group**: `redis-cli XINFO GROUPS <stream-name>`
- [ ] **Message acknowledgment**: `redis-cli XPENDING <stream-name> <group-name>`
- [ ] **No message loss**: Restart worker and verify reprocessing
- [ ] **Batch processing**: Worker handles 100+ messages efficiently

### Redis Queue Health Check

```bash
#!/bin/bash
# tests/queue/verify-health.sh

echo "Checking Redis Streams health..."

# Check logs stream
LOGS_COUNT=$(redis-cli XLEN logs-stream 2>/dev/null || echo 0)
echo "Log stream entries: $LOGS_COUNT"

# Check metrics stream
METRICS_COUNT=$(redis-cli XLEN metrics-stream 2>/dev/null || echo 0)
echo "Metrics stream entries: $METRICS_COUNT"

# Check consumer groups
echo ""
echo "Log worker consumer group:"
redis-cli XINFO GROUPS logs-stream | grep -A 10 "log-worker-group"

echo ""
echo "Metrics worker consumer group:"
redis-cli XINFO GROUPS metrics-stream | grep -A 10 "metrics-worker-group"
```

## Kubernetes Manifest Testing (If Modified)

If modifying Kubernetes deployment manifests or Helm charts:

- [ ] **Syntax validation**: `kubctl apply --dry-run=client -f manifests/`
- [ ] **Helm validation**: `helm lint helm/killkrill/`
- [ ] **Security scanning**: `kubesec scan manifests/*.yaml`
- [ ] **Resource limits**: All pods have CPU/memory limits
- [ ] **Health checks**: Liveness and readiness probes configured

## Screenshot & Documentation Requirements

### Prerequisites
Before capturing screenshots, ensure development environment is running with mock data:

```bash
make dev                   # Start all services
make seed-mock-data       # Populate with test logs and metrics
```

### Capture Screenshots
For all UI changes, update screenshots to show current application state with realistic data:

```bash
node scripts/capture-screenshots.cjs
# Or via npm script if configured: npm run screenshots
```

### What to Screenshot (Manager UI)
- **Login page** (unauthenticated state)
- **Dashboard** with realistic mock logs and metrics
  - 3-4 representative log entries
  - 3-4 representative metrics
  - Various states/levels when applicable
- **All feature pages** with realistic data:
  - Source management pages
  - Log viewing/filtering
  - Metrics dashboards
  - Worker status pages
  - Empty states vs populated views

### Commit Guidelines
- Automatically removes old screenshots and captures fresh ones
- Commit updated screenshots with relevant feature/UI/documentation changes
- Screenshots demonstrate feature purpose and functionality
- Helpful error message if login fails: "Ensure mock data is seeded"

---

**Last Updated**: 2026-01-06
**Maintained by**: Penguin Tech Inc
**Next Review**: 2026-02-06
