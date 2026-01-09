# Testing Strategy & Separation

This document outlines the comprehensive testing strategy for Killkrill, with clear separation between:

1. **CI/GHA Tests** - Automated tests in GitHub Actions (no container dependencies)
2. **Local Pre-Commit Tests** - Developer machine tests with full environment
3. **E2E/Smoke Tests** - Integration tests against running clusters

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TESTING PYRAMID                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                        E2E/Integration Tests                        │
│                     (Local, Pre-Commit, Manual)                    │
│                     - Running cluster tests                         │
│                     - API health checks                             │
│                     - Data pipeline validation                      │
│                                                                      │
│                     Unit Tests (CI & Local)                         │
│                  (Fast, Mocked, No Container Deps)                 │
│                     - Go unit tests                                 │
│                     - Python unit tests                             │
│                     - JavaScript/TypeScript tests                   │
│                                                                      │
│                    Linting & Security (CI Only)                     │
│              (Static Analysis, No Containers Needed)               │
│                  - ESLint, Prettier, golangci-lint                 │
│                  - Trivy, CodeQL, Semgrep, Bandit                  │
│                  - Dependency audits (npm, go mod)                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Test Categories

### 1. CI/GHA Tests (GitHub Actions)

**Location:** `.github/workflows/ci.yml`, `.github/workflows/docker-build.yml`

**Requirements:**

- ✅ **No container runtime dependencies**
- ✅ **No external services required** (PostgreSQL, Redis, etc.)
- ✅ **Fast execution** (< 10 minutes per workflow)
- ✅ **Deterministic** (same results every run)
- ✅ **Can run on any branch** (no main branch dependency)

**What Runs in CI:**

#### Linting & Code Quality

```yaml
- Go: golangci-lint, go vet, staticcheck
- Python: black, isort, flake8, mypy
- Node.js: ESLint, Prettier
- Dockerfile: hadolint
```

#### Security Scanning

```yaml
- Trivy filesystem scanning
- CodeQL analysis (Go, Python, JavaScript)
- Semgrep pattern matching
- Bandit (Python)
- npm audit, go mod verify
```

#### Unit Tests (Mocked Dependencies)

```yaml
- Go: go test -short ./...
- Python: pytest -m "not integration" (mocked DB/Redis)
- Node.js: npm test (no external services)
```

#### Docker Builds & Image Scanning

```yaml
- Build multi-arch images (amd64, arm64)
- Trivy scan of built container images
- Push to registry (on main/tags only)
```

#### License Validation

```yaml
- Verify license client files exist
- Check license server configuration
```

**What Does NOT Run in CI:**

- ❌ Integration tests (require running services)
- ❌ E2E smoke tests (require running cluster)
- ❌ Performance tests (require full environment)
- ❌ End-to-end user workflows
- ❌ Docker-compose with multiple containers
- ❌ Database migrations & schema setup

---

### 2. Local Pre-Commit Tests

**Location:** `scripts/pre-commit-checklist.sh`

**Purpose:** Comprehensive validation before pushing code, run on developer machine

**Requirements:**

- ✅ **Full Docker/container support** (docker, docker-compose)
- ✅ **All languages installed** (Go, Python, Node.js)
- ✅ **Can run full integration tests** (PostgreSQL, Redis, etc.)
- ✅ **Catches issues before GHA** (faster feedback loop)
- ✅ **Optional skip flags** (--skip-docker, --skip-integration)

**What Runs:**

#### Phase 1: Pre-Flight Checks

```bash
✓ Required tools installed (git, docker, go, python, npm)
✓ Working directory state check
```

#### Phase 2: Linting & Code Quality

```bash
✓ golangci-lint (Go)
✓ black, isort, flake8, mypy (Python)
✓ npm lint, prettier (JavaScript/TypeScript)
```

#### Phase 3: Unit Tests (Mocked)

```bash
✓ go test -v -short ./...
✓ pytest -m "not integration" (Python)
✓ npm test (Node.js)
```

#### Phase 4: Security Scanning

```bash
✓ Trivy filesystem scan
✓ Bandit (Python security)
✓ npm audit (dependency vulnerabilities)
✓ govulncheck (Go dependency vulnerabilities)
```

#### Phase 5: Integration Tests (WITH CONTAINERS)

```bash
✓ Start docker-compose.dev.yml
✓ pytest -m "integration" (with live database/cache)
✓ API integration tests
✓ Data pipeline tests
```

#### Phase 6: Build Verification

```bash
✓ go build ./apps/api
✓ npm run build (Node.js)
```

#### Phase 7: Dependency Security

```bash
✓ npm audit --audit-level=moderate
✓ govulncheck ./...
```

**Usage:**

```bash
# Run full pre-commit checklist
./scripts/pre-commit-checklist.sh

# Skip Docker/integration tests (quick CI-like mode)
./scripts/pre-commit-checklist.sh --skip-docker

# Skip only integration tests (but keep docker running)
./scripts/pre-commit-checklist.sh --skip-integration
```

**Exit Codes:**

- `0` = All checks passed, safe to commit
- `1` = One or more checks failed, fix issues before commit

---

### 3. E2E/Smoke Tests

**Location:** `scripts/e2e-smoke-tests.sh`

**Purpose:** Validate system behavior against running clusters (for manual testing, staging verification)

**Requirements:**

- ✅ **Full cluster environment** (docker-compose or Kubernetes)
- ✅ **Running services** (API, web, Python app, database, cache)
- ✅ **Health checks** (all services healthy before testing)
- ✅ **User-level validation** (actual HTTP requests, real data)

**What Tests:**

#### Service Health

```bash
✓ API /health endpoint
✓ Web /health endpoint
✓ Python app /health endpoint
✓ Metrics endpoints
```

#### API Functionality

```bash
✓ GET /api/v1/status
✓ GET /api/v1/features
✓ GET /api/v1/logs (data pipeline)
✓ GET /api/v1/metrics (data pipeline)
```

#### License Integration

```bash
✓ License features accessible
✓ Feature gating works
```

#### Error Handling

```bash
✓ 404 responses
✓ Error message formatting
```

#### Performance Baseline

```bash
✓ API response time < 1000ms (good)
✓ Warn if > 5000ms (slow)
```

#### Database Connectivity

```bash
✓ Data is persisted
✓ Queries return results
```

**Usage:**

```bash
# Test against docker-compose dev environment
./scripts/e2e-smoke-tests.sh dev

# Test against production-like docker-compose
./scripts/e2e-smoke-tests.sh docker

# Test against Kubernetes cluster
./scripts/e2e-smoke-tests.sh k8s
```

---

## Test Decision Matrix

**When deciding which test to write, use this matrix:**

| Test Type             | Unit          | Lint            | Security       | Integration             | E2E            | Location |
| --------------------- | ------------- | --------------- | -------------- | ----------------------- | -------------- | -------- |
| **Where**             | GHA + Local   | GHA + Local     | GHA + Local    | Local only              | Local only     |
| **When**              | Always        | Always          | Always         | Pre-commit              | Manual/staging |
| **Duration**          | Fast (<1s)    | Fast (<1s)      | Medium (1-10s) | Medium (10-60s)         | Slow (30s-5m)  |
| **External Services** | None (mocked) | None            | None           | All (PostgreSQL, Redis) | All            |
| **Docker Required**   | No            | No              | No             | Yes                     | Yes            |
| **Runs in GHA**       | Yes           | Yes             | Yes            | No                      | No             |
| **Example**           | `test_api.go` | `black --check` | `trivy fs .`   | `test_integration.py`   | Health checks  |

## CI/GHA Workflow Structure

### `ci.yml` - Core Tests (NO CONTAINER DEPS)

```yaml
jobs:
  changes:
    # Detect what changed (go/python/node/web/docs)

  go-test:
    # go vet, staticcheck, gosec, go test -short
    # NO services section (no postgres/redis)

  python-test:
    # black, isort, flake8, mypy, pytest (unit tests only)
    # NO services section (no postgres/redis)

  node-test:
    # ESLint, Prettier, type check, npm test
    # NO docker or external services

  security:
    # Trivy, CodeQL, Semgrep (filesystem scanning)
    # NO container builds needed

  license-check:
    # Verify license integration files

  test-summary:
    # Report results (no integration tests mentioned)
```

### `docker-build.yml` - Container Tests

```yaml
jobs:
  build-and-push:
    # Build multi-arch images
    # Push to registry (non-PR only)

  security-scan:
    # Trivy scan of built images
    # Runs only on main/tags

  release:
    # Create GitHub releases
    # Runs on version tags

  cleanup:
    # Delete untagged images
```

**Removed from CI:**

- ❌ `integration-test` job (moved to local pre-commit)
- ❌ `performance-test` job (moved to local pre-commit)

---

## Local Development Workflow

### Step 1: Before Committing

```bash
# Full pre-commit checklist (comprehensive)
./scripts/pre-commit-checklist.sh

# Or quick mode (skip docker)
./scripts/pre-commit-checklist.sh --skip-docker
```

**What happens:**

1. Linting & code quality checks
2. Unit tests (mocked dependencies)
3. Security scanning
4. Integration tests (if docker available)
5. Build verification
6. Dependency security

### Step 2: After Pushing

- GHA automatically runs CI tests
- Same linting, security, unit tests
- Fails if any check fails (blocks merge)

### Step 3: Before Merging

- All GHA checks must pass
- Manual code review
- Optional: Run E2E smoke tests against staging

### Step 4: Post-Merge

- Automated deployment to staging
- Manual E2E/smoke test verification
- Canary deployment to production

---

## Writing Tests

### Unit Test Pattern (Mocked Dependencies)

**Good - Mocked (runs in both GHA and local):**

```python
# tests/test_api.py
import pytest
from unittest.mock import MagicMock, patch

def test_api_status():
    """Unit test with mocked database"""
    with patch('app.db.query') as mock_db:
        mock_db.return_value = {'status': 'healthy'}
        response = client.get('/api/v1/status')
        assert response.status_code == 200
```

**Bad - Real database (GHA will fail):**

```python
def test_api_status():
    """Integration test - don't put in CI!"""
    # Uses real PostgreSQL
    response = client.get('/api/v1/status')
    assert response.status_code == 200
```

**Mark integration tests properly:**

```python
@pytest.mark.integration
def test_data_pipeline_with_real_db():
    """Integration test - runs locally only"""
    # Uses real services
    pass
```

### Security Test Pattern

**Good - Static analysis (runs in GHA):**

```bash
# In ci.yml
- name: Run Trivy scan
  run: trivy fs --exit-code 0 .

- name: Run CodeQL
  uses: github/codeql-action/analyze@v3
```

**Bad - Dynamic security testing (local only):**

```bash
# Don't put in CI - requires running server
- name: Run OWASP ZAP scan
  run: zaproxy /api/v1/users  # Requires API running!
```

### Integration Test Pattern

**Good location: `scripts/pre-commit-checklist.sh`**

```bash
if [ "$SKIP_DOCKER" = false ]; then
    docker-compose -f docker-compose.dev.yml up -d
    pytest -m integration
    docker-compose down -v
fi
```

**Bad location: `.github/workflows/ci.yml`**

```yaml
# DON'T DO THIS - requires docker services
services:
  postgres:
    image: postgres:15
  redis:
    image: redis:7
```

---

## Troubleshooting

### "Integration test failed in local pre-commit"

**Likely cause:** Database/cache not running

**Fix:**

```bash
# Ensure docker-compose is running
docker-compose -f docker-compose.dev.yml up -d

# Or skip integration tests
./scripts/pre-commit-checklist.sh --skip-docker
```

### "GHA tests pass but local tests fail"

**Likely cause:** Version mismatch (Go, Python, Node.js)

**Fix:**

```bash
# Match GHA versions
go version  # Should be 1.23.5 or 1.24.0
python3 --version  # Should be 3.12 or 3.13
node --version  # Should be 18, 20, or 22
```

### "Security scan fails in GHA but passes locally"

**Likely cause:** Database/cache not properly mocked in local tests

**Solution:**

1. Run tests in mocked mode: `pytest -m "not integration"`
2. Verify no external service calls in unit tests
3. Mock all I/O in unit tests

### "Performance test takes too long locally"

**Expected behavior:** E2E tests are slow (30s-5m)

**To speed up pre-commit:**

```bash
./scripts/pre-commit-checklist.sh --skip-docker
```

---

## CI/GHA Secrets & Configuration

### Required Secrets

```yaml
GITHUB_TOKEN: Automatic (no configuration needed)
```

### Workflow Variables

```yaml
GO_VERSION: "1.23.5"
PYTHON_VERSION: "3.12"
NODE_VERSION: "18"
```

---

## Performance Targets

| Test Category     | Target Time | Acceptable | Warn If |
| ----------------- | ----------- | ---------- | ------- |
| Linting           | <30s        | <1m        | >2m     |
| Unit tests        | <2m         | <5m        | >10m    |
| Security scan     | <1m         | <3m        | >5m     |
| GHA total         | <10m        | <15m       | >20m    |
| Integration tests | <5m         | <10m       | >15m    |
| Pre-commit total  | <15m        | <30m       | >45m    |
| E2E smoke tests   | <5m         | <10m       | >15m    |

---

## References

- [Contributing Guide](./CONTRIBUTING.md)
- [Development Standards](./STANDARDS.md)
- [Workflow Documentation](./WORKFLOWS.md)
- [Project README](../README.md)
