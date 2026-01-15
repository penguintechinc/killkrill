# Killkrill CI/CD Workflows

Comprehensive documentation for all killkrill GitHub Actions workflows with .WORKFLOW compliance features.

## Overview

Killkrill is a data processing system with 7 containerized services optimized for Kubernetes deployment:

| Service              | Type         | Language | Purpose                                          |
| -------------------- | ------------ | -------- | ------------------------------------------------ |
| **API**              | REST Service | Go       | Main API gateway for data submission and queries |
| **Log-Worker**       | Worker       | Python   | Processes log data from message queue            |
| **Metrics-Worker**   | Worker       | Python   | Processes metrics data and aggregations          |
| **Log-Receiver**     | Receiver     | Python   | Ingests log entries via syslog/HTTP              |
| **Metrics-Receiver** | Receiver     | Python   | Ingests metrics via HTTP/Prometheus format       |
| **K8s-Operator**     | Operator     | Go       | Kubernetes operator for killkrill management     |
| **K8s-Agent**        | Sidecar      | Go       | Per-pod agent for data collection                |

## Workflow Files

### Core Workflows

| Workflow              | Trigger                                 | Purpose                                |
| --------------------- | --------------------------------------- | -------------------------------------- |
| `ci.yml`              | Push/PR to main/develop, daily schedule | Unit tests, security scanning, linting |
| `docker-build.yml`    | Push to main/develop, version tags      | Multi-arch container builds            |
| `version-release.yml` | Push to `.version` file                 | Automatic pre-release creation         |
| `push.yml`            | Push to main                            | Publish images to registry             |
| `release.yml`         | GitHub release published                | Publish release-tagged images          |
| `deploy.yml`          | Push to main, workflow_dispatch         | Deploy to staging/production           |
| `cron.yml`            | Daily schedule                          | Automated maintenance tasks            |
| `gitstream.yml`       | All events                              | PR automation and management           |

---

## Continuous Integration (ci.yml)

### Trigger Conditions

```yaml
on:
  push:
    branches: [ main, develop, feature/* ]
    paths:
      - '.version'
      - 'go.mod', 'go.sum', '**/*.go'
      - 'apps/**'
      - 'requirements.txt', '**/*.py'
      - 'package.json', 'package-lock.json'
      - '**/*.js', '**/*.ts', '**/*.tsx'
      - '.github/workflows/ci.yml'
  pull_request:
    branches: [ main, develop ]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

### Features

#### Version Detection

- Reads `.version` file to determine current version
- Falls back to `0.0.0` if file missing
- Used for tagging and metadata generation

#### Epoch64 Timestamp Generation

- Generates millisecond-precision timestamp: `date +%s%N | cut -b1-13`
- Used for chronological ordering between releases
- Enables unique build identification

#### Changes Detection

- Skips jobs when unrelated files change
- Separate triggers for Go, Python, Node.js, web, and docs changes
- Accelerates CI/CD pipeline for focused changes

### Jobs

#### 1. Go Testing and Linting (go-test)

**Conditions**: When Go files modified

**Actions**:

- Tests against Go 1.23.5 and 1.24.0
- `go mod download` - Download dependencies
- `go mod verify` - Verify dependency checksums
- `go vet ./...` - Static analysis
- `staticcheck` - Code quality checks
- **gosec security scanning** - Security vulnerability detection
  - Output: JSON format → SARIF for GitHub Security tab
  - Continues on error for non-blocking scanning
- `go test -race` - Race condition detection
- Coverage reporting to Codecov

**Services Covered**:

- `apps/api` (Go REST API)
- `apps/k8s-operator` (Kubernetes operator)
- `apps/k8s-agent` (Pod-level agent)

#### 2. Python Testing and Linting (python-test)

**Conditions**: When Python files modified

**Actions**:

- Tests against Python 3.12 and 3.13
- Spins up PostgreSQL 15 and Redis 7 services
- Dependency installation with `pip install -r requirements.txt`
- **Code formatting**:
  - `black --check` - Code style
  - `isort --check-only` - Import sorting
  - `flake8` - Linting
  - `mypy` - Type checking (non-blocking)
- **bandit security scanning** - Python security analyzer
  - Skips B101 (assert_used) and B601 (paramiko_calls)
  - JSON output for further analysis
  - Continues on error for non-blocking scanning
- `pytest` - Unit testing with coverage
- Codecov upload

**Services Covered**:

- `apps/log-worker` (Python worker)
- `apps/metrics-worker` (Python worker)
- `apps/log-receiver` (Python receiver)
- `apps/metrics-receiver` (Python receiver)
- `apps/manager` (Python management service)

#### 3. Node.js/Web Testing (node-test)

**Conditions**: When JavaScript/TypeScript/web files modified

**Actions**:

- Tests against Node.js 18, 20, 22
- `npm ci` - Clean dependency installation
- ESLint - JavaScript linting
- Prettier - Code formatting check
- Type checking - TypeScript validation
- `npm test` - Unit testing
- `npm run build` - Build validation
- Artifact upload for build outputs

#### 4. Integration Testing (integration-test)

**Conditions**: All language tests pass

**Actions**:

- Sets up PostgreSQL 15 and Redis 7
- Builds all service types
- Verifies API health endpoints: `/health`, `/metrics`
- Tests feature endpoints
- Validates license integration
- E2E tests if `tests/e2e/` exists

#### 5. Security Scanning (security)

**Actions**:

- Trivy filesystem vulnerability scan
- CodeQL analysis for Go, Python, JavaScript
- Semgrep static analysis with OWASP rules
- SARIF output for GitHub Security tab integration

#### 6. License Validation (license-check)

**Actions**:

- Verifies license client integration
- Checks for license server references
- Validates client library presence

#### 7. Test Summary (test-summary)

**Actions**:

- Aggregates all test results
- Comments on PR with summary
- Uploads test artifacts
- Fails if any required test fails

---

## Docker Build Pipeline (docker-build.yml)

### Trigger Conditions

```yaml
on:
  push:
    branches: [main, develop]
    tags: ["v*"]
    paths:
      - ".version"
      - "apps/**"
      - "Dockerfile"
      - "docker-compose.yml"
      - ".github/workflows/docker-build.yml"
  pull_request:
    branches: [main]
```

### Build Strategy

- **Multi-architecture support**: amd64, arm64
- **Service matrix**: Builds all services in parallel
- **Caching**: Layer caching via GitHub Actions cache
- **Base images**: Debian-slim for minimal footprint

### Services Built

```yaml
strategy:
  matrix:
    service:
      - name: api
        dockerfile: apps/api/Dockerfile
        context: .
      - name: log-worker
        dockerfile: apps/log-worker/Dockerfile
        context: .
      - name: metrics-worker
        dockerfile: apps/metrics-worker/Dockerfile
        context: .
      - name: log-receiver
        dockerfile: apps/log-receiver/Dockerfile
        context: .
      - name: metrics-receiver
        dockerfile: apps/metrics-receiver/Dockerfile
        context: .
      - name: manager
        dockerfile: apps/manager/Dockerfile
        context: .
```

### Version and Timestamp Detection

All builds include:

- **Version string**: From `.version` file
- **Epoch64 timestamp**: Current millisecond timestamp
- **Metadata labels**: Container labels with version info
- **Image tagging**: Conditional based on branch

### Security Scanning

- Trivy scans built images for vulnerabilities
- Results uploaded to GitHub Security tab
- SARIF format integration

### Artifact Management

- Automatic cleanup of untagged images
- Image retention policies via GitHub Container Registry settings
- Build cache pruning on schedule

---

## Version Release Workflow (version-release.yml)

### Trigger

```yaml
on:
  push:
    branches:
      - main
    paths:
      - ".version"
```

### Process

1. **Version Detection**:
   - Reads `.version` file
   - Extracts semantic version (major.minor.patch)
   - Skips if version is `0.0.0` (default)

2. **Release Check**:
   - Verifies release doesn't already exist
   - Uses GitHub CLI for release management

3. **Release Notes Generation**:
   - Includes version details
   - Git commit and branch information
   - Changelog stub for manual updates

4. **Pre-release Creation**:
   - Creates pre-release tag
   - Marks as pre-release for testing
   - Updates repository release list

### Usage

```bash
# Update .version file
echo "1.2.3" > .version
git add .version
git commit -m "Release v1.2.3"
git push origin main

# Automatically creates GitHub pre-release v1.2.3
```

---

## Push Workflow (push.yml)

### Trigger

```yaml
on:
  push:
    branches: ["main"]
    paths:
      - ".version"
      - "apps/**"
      - "Dockerfile"
      - "docker-compose.yml"
      - ".github/workflows/push.yml"
```

### Actions

1. **Version Detection**: Determines current version
2. **Ansible Lint**: Validates infrastructure as code
3. **Docker Build & Push**:
   - Latest tag on main branch
   - Branch-based naming (main → latest)
   - Multi-architecture builds
   - Cache optimization
4. **Codecov Upload**: Coverage report submission

---

## Release Workflow (release.yml)

### Trigger

```yaml
on:
  release:
    types: [published]
```

### Actions

1. **Version Extraction**: From release tag (v1.2.3 → 1.2.3)
2. **Docker Build & Push**:
   - Semantic version tags (1.2.3, 1.2, 1)
   - Latest tag
   - Both full and short versions
3. **Release Notes**: Appends image information to release

---

## Deploy Workflow (deploy.yml)

### Triggers

```yaml
on:
  push:
    branches: [main]
    tags: ["v*"]
    paths:
      - ".version"
      - "apps/**"
      - "k8s/**"
      - ".github/workflows/deploy.yml"
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, production]
      version:
        description: "Version/tag to deploy"
        default: "main"
```

### Deployment Strategy

#### Staging Deployment

- **Trigger**: Every push to main
- **Target**: Staging environment
- **Process**: ECS task update with new image
- **Health checks**: Waits for service stabilization

#### Production Deployment

- **Trigger**: Manual workflow_dispatch or version tags
- **Target**: Production environment (k8s-ready)
- **Process**: Blue-green deployment with rollback capability
- **Validation**: Post-deployment health checks

### Kubernetes Integration

Killkrill is Kubernetes-ready with:

- **Helm charts**: Located in `helm/` directory
- **Manifests**: Kubernetes YAML in `k8s/` directory
- **Health checks**: Liveness and readiness probes
- **Resource limits**: Defined per service
- **Service mesh**: Optional Istio integration
- **Configuration**: ConfigMaps and Secrets
- **RBAC**: Service accounts and permissions

---

## Scheduled Tasks (cron.yml)

### Daily Maintenance (0 2 \* \* \* UTC)

Runs scheduled maintenance tasks:

- Dependency vulnerability checks
- Container image scanning
- Log rotation and cleanup
- Database maintenance tasks
- Security audit logs

---

## PR Automation (gitstream.yml)

### Automated Actions

- PR author assignment
- Automatic labeling based on file changes
- Reviewer assignment
- Draft PR handling
- Merge conflict detection

---

## Security Scanning Details

### Gosec (Go Security Scanner)

**Configuration**:

```
-no-fail: Continue on findings
-fmt json: JSON output
./...: Scan all packages
```

**Issues Detected**:

- SQL injection vulnerabilities
- Hardcoded credentials
- Weak cryptography
- Insecure HTTP usage
- Race conditions
- Command injection

**Integration**: GitHub Security tab via SARIF upload

### Bandit (Python Security Scanner)

**Configuration**:

```
Skip B101: assert_used (OK in tests)
Skip B601: paramiko_calls (false positives)
```

**Issues Detected**:

- Hardcoded passwords/tokens
- Insecure deserialization
- Unsafe YAML parsing
- SQL injection risks
- Weak cryptography
- Command execution issues

**Integration**: JSON output for analysis

---

## Metadata and Labels

All container builds include standardized OCI labels:

```
org.opencontainers.image.version     → From .version
org.opencontainers.image.created     → Build timestamp
org.opencontainers.image.revision    → Git commit SHA
org.opencontainers.image.source      → Repository URL
org.opencontainers.image.description → Service description
org.opencontainers.image.title       → Service name
```

---

## Environment Variables

### CI/CD Environment Variables

| Variable         | Source  | Usage                        |
| ---------------- | ------- | ---------------------------- |
| `GITHUB_TOKEN`   | Secrets | Registry authentication      |
| `REGISTRY`       | Env     | Container registry (ghcr.io) |
| `GO_VERSION`     | Env     | Go testing version           |
| `PYTHON_VERSION` | Env     | Python testing version       |
| `NODE_VERSION`   | Env     | Node.js testing version      |

### Service-specific Variables (Runtime)

See individual service documentation for runtime environment configuration.

---

## Troubleshooting

### Workflow Not Triggering

1. Check file path filters in `on.push.paths`
2. Verify branch matches trigger conditions
3. Review `.github/workflows/*.yml` syntax
4. Confirm personal access tokens (if applicable)

### Build Failures

**Go builds fail**:

- Check `go.mod` and `go.sum` are in sync
- Verify `go.version` file exists and is readable
- Run `go mod tidy` locally before push

**Python builds fail**:

- Verify `requirements.txt` is present
- Check for Python version compatibility
- Run `pip install -r requirements.txt` locally

**Docker builds fail**:

- Verify Dockerfile base images exist
- Check for missing COPY/ADD files
- Confirm build context is correct

### Security Scan False Positives

**Gosec**:

- Add `// #nosec` comments for intentional vulnerabilities
- Use `gosec` config file for baseline suppression

**Bandit**:

- Add `# nosec` to skip individual lines
- Use `.bandit` file for project-wide configuration

---

## Performance Tips

### Workflow Optimization

- Use `paths` filters to skip unnecessary jobs
- Enable caching for dependencies
- Run tests in parallel with strategy matrix
- Use `needs` for explicit job dependencies

### Build Optimization

- Layer caching via `docker/build-push-action`
- Multi-stage Dockerfiles with minimal runtime images
- Debian-slim base images (vs. alpine for compatibility)
- Parallel multi-arch builds

### Cost Optimization

- Concurrency control prevents duplicate runs
- Untagged image cleanup prevents registry bloat
- Scheduled cleanup tasks during off-peak hours
- Resource quotas on self-hosted runners

---

## Compliance Checklist

- [x] `.version` file triggers tracked in all workflows
- [x] Epoch64 timestamp generation in all build jobs
- [x] Version detection step in all workflows
- [x] Gosec scanning enabled for Go services
- [x] Bandit scanning enabled for Python services
- [x] Metadata labels with version and timestamp
- [x] Conditional logic for version-based tagging
- [x] Multi-architecture builds (amd64, arm64)
- [x] Container security scanning (Trivy)
- [x] SARIF format for GitHub Security integration

---

## Reference

- **GitHub Actions**: https://docs.github.com/en/actions
- **Container Registry**: https://docs.github.com/en/packages/container-registry
- **Gosec**: https://github.com/securego/gosec
- **Bandit**: https://bandit.readthedocs.io/
- **Trivy**: https://aquasecurity.github.io/trivy/
- **OCI Image Spec**: https://github.com/opencontainers/image-spec
