# Killkrill - Claude Code Context

## Project Overview

Killkrill is an enterprise-grade data processing and observability system built on modern distributed architecture patterns. It provides high-performance log and metrics ingestion, processing, and querying with Kubernetes-native deployment.

**Project Features:**
- High-performance Go services (API, K8s Operator, K8s Agent)
- Python workers and receivers for data processing (log/metrics)
- Web-based management and monitoring (Python + React)
- Kubernetes-native deployment with Helm charts
- Multi-container architecture with independent scaling
- Comprehensive CI/CD pipeline with multi-arch builds
- PenguinTech License Server integration

## Technology Stack

### Languages & Frameworks

**Killkrill Technology Choices:**
- **Go 1.23.x**: High-performance services requiring >10K req/sec
  - API service: REST endpoints, request routing, query handling
  - K8s Operator: Custom resource reconciliation
  - K8s Agent: Per-pod sidecar for coordination
- **Python 3.12+**: Data processing and web services
  - Worker services: Event/log/metrics processing
  - Receiver services: Data ingestion (Syslog, HTTP, Prometheus)
  - Manager service: Web UI and administrative API
- **Node.js + React**: Frontend for manager UI
  - Dashboard and monitoring views
  - Configuration management
  - User authentication and RBAC

**Python Stack:**
- **Python**: 3.12+ for all applications
- **Web Framework**: Quart with Hypercorn server (mandatory async framework)
- **Database ORM**: Hybrid approach - SQLAlchemy for initialization, PyDAL for day-to-day operations (mandatory for all Python applications)
- **Performance**: Dataclasses with slots, type hints, async/await required
- **Server**: Hypercorn ASGI server for production deployments

**Frontend Stack:**
- **React**: ReactJS for all frontend applications
- **Node.js**: 18+ for build tooling and React development
- **JavaScript/TypeScript**: Modern ES2022+ standards

**Go Stack (When Required):**
- **Go**: 1.23.x (latest patch version)
- **Database**: Use DAL with PostgreSQL/MySQL cross-support (e.g., GORM, sqlx)
- Use only for traffic-intensive applications

### Infrastructure & DevOps
- **Containers**: Docker with multi-stage builds, Docker Compose
- **Orchestration**: Kubernetes with Helm charts
- **Configuration Management**: Ansible for infrastructure automation
- **CI/CD**: GitHub Actions with comprehensive pipelines
- **Monitoring**: Prometheus metrics, Grafana dashboards
- **Logging**: Structured logging with configurable levels

### Databases & Storage
- **Primary**: PostgreSQL (default, configurable via `DB_TYPE` environment variable)
- **Cache**: Redis/Valkey with optional TLS and authentication
- **Database Abstraction Layers (DALs)**:
  - **Python**: PyDAL (mandatory for ALL Python applications)
    - Must support ALL PyDAL-supported databases by default
    - Special support for MariaDB Galera cluster requirements
    - `DB_TYPE` must match PyDAL connection string prefixes exactly
  - **Go**: GORM or sqlx (mandatory for cross-database support)
    - Must support PostgreSQL and MySQL/MariaDB
    - Stable, well-maintained library required
- **Migrations**: Automated schema management
- **Database Support**: Design for ALL PyDAL-supported databases from the start
- **MariaDB Galera Support**: Handle Galera-specific requirements (WSREP, auto-increment, transactions)

**Supported DB_TYPE Values (PyDAL prefixes)**:
- `postgres` - PostgreSQL (default)
- `mysql` - MySQL/MariaDB
- `sqlite` - SQLite

**MariaDB Galera Cluster Requirements**:
- Connection pooling with sticky sessions for consistent reads
- WSREP synchronization control via `wsrep_sync_wait` for read-your-writes consistency
- Auto-increment offset configuration for multi-node writes (WSREP_ON=ON)
- Transaction isolation level: REPEATABLE-READ (Galera default)
- Avoid explicit LOCK commands in transactions
- Connection retry logic for temporary node unavailability
- Environment variables: `GALERA_MODE=true`, `GALERA_NODES=node1,node2,node3`

### Security & Authentication
- **Quart-JWT or Custom Auth**: Authentication for Quart applications
  - Role-based access control (RBAC) via decorators
  - JWT token-based authentication and session management
  - Password hashing with bcrypt
  - Email confirmation and password reset
  - Two-factor authentication (2FA)
- **TLS**: Enforce TLS 1.2 minimum, prefer TLS 1.3
- **HTTP3/QUIC**: Utilize UDP with TLS for high-performance connections where possible
- **Authentication**: JWT and MFA (standard), mTLS where applicable
- **SSO**: SAML/OAuth2 SSO as enterprise-only features
- **Secrets**: Environment variable management
- **Scanning**: Trivy vulnerability scanning, CodeQL analysis
- **Code Quality**: All code must pass CodeQL security analysis

## PenguinTech License Server Integration

All projects integrate with the centralized PenguinTech License Server at `https://license.penguintech.io` for feature gating and enterprise functionality.

**IMPORTANT: License enforcement is ONLY enabled when project is marked as release-ready**
- Development phase: All features available, no license checks
- Release phase: License validation required, feature gating active

**License Key Format**: `PENG-XXXX-XXXX-XXXX-XXXX-ABCD`

**Core Endpoints**:
- `POST /api/v2/validate` - Validate license
- `POST /api/v2/features` - Check feature entitlements
- `POST /api/v2/keepalive` - Report usage statistics

**Environment Variables**:
```bash
# License configuration
LICENSE_KEY=PENG-XXXX-XXXX-XXXX-XXXX-ABCD
LICENSE_SERVER_URL=https://license.penguintech.io
PRODUCT_NAME=your-product-identifier

# Release mode (enables license enforcement)
RELEASE_MODE=false  # Development (default)
RELEASE_MODE=true   # Production (explicitly set)
```

📚 **Detailed Documentation**: [License Server Integration Guide](docs/licensing/license-server-integration.md)

## WaddleAI Integration (Optional)

For projects requiring AI capabilities, integrate with WaddleAI located at `~/code/WaddleAI`.

**When to Use WaddleAI:**
- Natural language processing (NLP)
- Machine learning model inference
- AI-powered features and automation
- Intelligent data analysis
- Chatbots and conversational interfaces

**Integration Pattern:**
- WaddleAI runs as separate microservice container
- Communicate via REST API or gRPC
- Environment variable configuration for API endpoints
- License-gate AI features as enterprise functionality

📚 **WaddleAI Documentation**: See WaddleAI project at `~/code/WaddleAI` for integration details

## Project Structure

```
killkrill/
├── .github/              # CI/CD pipelines and templates
│   └── workflows/        # GitHub Actions for each service
├── apps/                 # Microservices (separate containers)
│   ├── api/              # Go REST API service (10K+ req/sec)
│   ├── log-worker/       # Python worker for log processing
│   ├── metrics-worker/   # Python worker for metrics processing
│   ├── log-receiver/     # Python service for log ingestion
│   ├── metrics-receiver/ # Python service for metrics ingestion
│   ├── manager/          # Python Flask + React manager service
│   ├── k8s-operator/     # Go Kubernetes operator
│   └── k8s-agent/        # Go per-pod sidecar agent
├── k8s/                  # Kubernetes deployment templates
│   ├── helm/             # Helm v3 charts per service
│   ├── manifests/        # Raw K8s manifests
│   └── kustomize/        # Kustomize overlays
├── config/               # Configuration files
├── scripts/              # Utility scripts
├── tests/                # Test suites (unit, integration, e2e)
├── docs/                 # Documentation
├── docker-compose.yml    # Production environment
├── docker-compose.dev.yml # Local development
├── Makefile              # Build automation
├── .version              # Version tracking
└── CLAUDE.md             # This file
```

### Multi-Service Architecture

Killkrill consists of multiple specialized microservices, each optimized for its role:

| Service | Language | Purpose | SLA |
|---------|----------|---------|-----|
| **api** | Go | REST API gateway, request routing | 10K+ req/sec, P99 <100ms |
| **log-worker** | Python | Process log entries asynchronously | 50K+ events/sec |
| **metrics-worker** | Python | Aggregate and process metrics | 50K+ events/sec |
| **log-receiver** | Python | High-throughput log ingestion | 100K+ msg/sec |
| **metrics-receiver** | Python | Prometheus/HTTP metrics ingestion | 100K+ msg/sec |
| **manager** | Python/React | Web UI and admin API | <500ms response time |
| **k8s-operator** | Go | Kubernetes custom resource operator | Sub-second reconciliation |
| **k8s-agent** | Go | Per-pod sidecar for coordination | <50MB memory |

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────┐         │
│  │   API Pod   │    │ Log Receiver│    │ Metrics Receiver Pod │         │
│  │  (Port 8080)│    │(Syslog/HTTP)│    │ (Prometheus/HTTP)    │         │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬───────────┘         │
│         │                  │                       │                    │
│         └──────────┬───────┴───────────────────────┘                    │
│                    ↓                                                     │
│         ┌──────────────────────┐                                         │
│         │  Message Queue       │                                         │
│         │  (Redis/Kafka)       │                                         │
│         └──────────┬───────────┘                                         │
│                    │                                                     │
│      ┌─────────────┼─────────────┐                                       │
│      ↓             ↓             ↓                                       │
│  ┌─────────┐ ┌─────────┐ ┌──────────────┐                              │
│  │Log Wkr  │ │Metrics  │ │Manager UI    │                              │
│  │   Pod   │ │Wkr Pod  │ │(Flask/React) │                              │
│  └────┬────┘ └────┬────┘ └──────┬───────┘                              │
│       │           │             │                                       │
│       └───────────┼─────────────┘                                       │
│                   ↓                                                     │
│          ┌────────────────┐                                             │
│          │  PostgreSQL    │                                             │
│          │  (K8s native)  │                                             │
│          └────────────────┘                                             │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Default Roles (WebUI)

| Role | Permissions |
|------|-------------|
| **Admin** | Full access: user CRUD, settings, all features |
| **Maintainer** | Read/write access to resources, no user management |
| **Viewer** | Read-only access to resources |

## Version Management System

**Format**: `vMajor.Minor.Patch.build`
- **Major**: Breaking changes, API changes, removed features
- **Minor**: Significant new features and functionality additions
- **Patch**: Minor updates, bug fixes, security patches
- **Build**: Epoch64 timestamp of build time

**Update Commands**:
```bash
./scripts/version/update-version.sh          # Increment build timestamp
./scripts/version/update-version.sh patch    # Increment patch version
./scripts/version/update-version.sh minor    # Increment minor version
./scripts/version/update-version.sh major    # Increment major version
```

## Development Workflow

### Local Development Setup
```bash
git clone <repository-url>
cd project-name
make setup                    # Install dependencies
make dev                      # Start development environment
```

### Essential Commands
```bash
# Development
make dev                      # Start development services
make test                     # Run all tests
make lint                     # Run linting
make build                    # Build all services
make clean                    # Clean build artifacts

# Production
make docker-build             # Build containers
make docker-push              # Push to registry
make deploy-dev               # Deploy to development
make deploy-prod              # Deploy to production

# Testing
make test-unit               # Run unit tests
make test-integration        # Run integration tests
make test-e2e                # Run end-to-end tests

# License Management
make license-validate        # Validate license
make license-check-features  # Check available features
```

## Critical Development Rules

### Development Philosophy: Safe, Stable, and Feature-Complete

**NEVER take shortcuts or the "easy route" - ALWAYS prioritize safety, stability, and feature completeness**

#### Core Principles
- **No Quick Fixes**: Resist quick workarounds or partial solutions
- **Complete Features**: Fully implemented with proper error handling and validation
- **Safety First**: Security, data integrity, and fault tolerance are non-negotiable
- **Stable Foundations**: Build on solid, tested components
- **Future-Proof Design**: Consider long-term maintainability and scalability
- **No Technical Debt**: Address issues properly the first time

#### Red Flags (Never Do These)
- ❌ Skipping input validation "just this once"
- ❌ Hardcoding credentials or configuration
- ❌ Ignoring error returns or exceptions
- ❌ Commenting out failing tests to make CI pass
- ❌ Deploying without proper testing
- ❌ Using deprecated or unmaintained dependencies
- ❌ Implementing partial features with "TODO" placeholders
- ❌ Bypassing security checks for convenience
- ❌ Assuming data is valid without verification
- ❌ Leaving debug code or backdoors in production

#### Quality Checklist Before Completion
- ✅ All error cases handled properly
- ✅ Unit tests cover all code paths
- ✅ Integration tests verify component interactions
- ✅ Security requirements fully implemented
- ✅ Performance meets acceptable standards
- ✅ Documentation complete and accurate
- ✅ Code review standards met
- ✅ No hardcoded secrets or credentials
- ✅ Logging and monitoring in place
- ✅ Build passes in containerized environment
- ✅ No security vulnerabilities in dependencies
- ✅ Edge cases and boundary conditions tested

### Git Workflow
- **NEVER commit automatically** unless explicitly requested by the user
- **NEVER push to remote repositories** under any circumstances
- **ONLY commit when explicitly asked** - never assume commit permission
- Always use feature branches for development
- Require pull request reviews for main branch
- Automated testing must pass before merge

**Before Every Commit - Security Scanning**:
- **Run security audits on all modified packages**:
  - **Go packages**: Run `gosec ./...` on modified Go services
  - **Node.js packages**: Run `npm audit` on modified Node.js services
  - **Python packages**: Run `bandit -r .` and `safety check` on modified Python services
- **Do NOT commit if security vulnerabilities are found** - fix all issues first
- **Document vulnerability fixes** in commit message if applicable

**Before Every Commit - API Testing**:
- **Create and run API testing scripts** for each modified container service
- **Testing scope**: All new endpoints and modified functionality
- **Test files location**: `tests/api/` directory with service-specific subdirectories
  - `tests/api/flask-backend/` - Flask backend API tests
  - `tests/api/go-backend/` - Go backend API tests
  - `tests/api/webui/` - WebUI container tests
- **Run before commit**: Each test script should be executable and pass completely
- **Test coverage**: Health checks, authentication, CRUD operations, error cases
- **Command pattern**: `cd services/<service-name> && npm run test:api` or equivalent

**Before Every Commit - Screenshots**:
- **Run screenshot tool to update UI screenshots in documentation**
  - Run `cd services/webui && npm run screenshots` to capture current UI state
  - This automatically removes old screenshots and captures fresh ones
  - Commit updated screenshots with relevant feature/documentation changes

### Local State Management (Crash Recovery)
- **ALWAYS maintain local .PLAN and .TODO files** for crash recovery
- **Keep .PLAN file updated** with current implementation plans and progress
- **Keep .TODO file updated** with task lists and completion status
- **Update these files in real-time** as work progresses
- **Add to .gitignore**: Both .PLAN and .TODO files must be in .gitignore
- **File format**: Use simple text format for easy recovery
- **Automatic recovery**: Upon restart, check for existing files to resume work

### Dependency Security Requirements
- **ALWAYS check for Dependabot alerts** before every commit
- **Monitor vulnerabilities via Socket.dev** for all dependencies
- **Mandatory security scanning** before any dependency changes
- **Fix all security alerts immediately** - no commits with outstanding vulnerabilities
- **Regular security audits**: `npm audit`, `go mod audit`, `safety check`

### Linting & Code Quality Requirements
- **ALL code must pass linting** before commit - no exceptions
- **Python**: flake8, black, isort, mypy (type checking), bandit (security)
- **JavaScript/TypeScript**: ESLint, Prettier
- **Go**: golangci-lint (includes staticcheck, gosec, etc.)
- **Ansible**: ansible-lint
- **Docker**: hadolint
- **YAML**: yamllint
- **Markdown**: markdownlint
- **Shell**: shellcheck
- **CodeQL**: All code must pass CodeQL security analysis
- **PEP Compliance**: Python code must follow PEP 8, PEP 257 (docstrings), PEP 484 (type hints)

### Build & Deployment Requirements
- **NEVER mark tasks as completed until successful build verification**
- All Go and Python builds MUST be executed within Docker containers
- Use containerized builds for local development and CI/CD pipelines
- Build failures must be resolved before task completion

### Documentation Standards
- **README.md**: Keep as overview and pointer to comprehensive docs/ folder
- **docs/ folder**: Create comprehensive documentation for all aspects
- **RELEASE_NOTES.md**: Maintain in docs/ folder, prepend new version releases to top
- Update CLAUDE.md when adding significant context
- **Build status badges**: Always include in README.md
- **ASCII art**: Include catchy, project-appropriate ASCII art in README
- **Company homepage**: Point to www.penguintech.io
- **License**: All projects use Limited AGPL3 with preamble for fair use

### File Size Limits
- **Maximum file size**: 25,000 characters for ALL code and markdown files
- **Split large files**: Decompose into modules, libraries, or separate documents
- **CLAUDE.md exception**: Maximum 39,000 characters (only exception to 25K rule)
- **High-level approach**: CLAUDE.md contains high-level context and references detailed docs
- **Documentation strategy**: Create detailed documentation in `docs/` folder and link to them from CLAUDE.md
- **Keep focused**: Critical context, architectural decisions, and workflow instructions only
- **User approval required**: ALWAYS ask user permission before splitting CLAUDE.md files
- **Use Task Agents**: Utilize task agents (subagents) to be more expedient and efficient when making changes to large files, updating or reviewing multiple files, or performing complex multi-step operations
- **Avoid sed/cat**: Use sed and cat commands only when necessary; prefer dedicated Read/Edit/Write tools for file operations

## Development Standards

Comprehensive development standards are documented separately to keep this file concise.

📚 **Complete Standards Documentation**: [Development Standards](docs/STANDARDS.md)

### Quick Reference

**API Versioning**:
- ALL REST APIs MUST use versioning: `/api/v{major}/endpoint` format
- Semantic versioning for major versions only in URL
- Support current and previous versions (N-1) minimum
- Add deprecation headers to old versions
- Document migration paths for version changes

**Database Standards**:
- PyDAL mandatory for ALL Python applications
- Thread-safe usage with thread-local connections
- Environment variable configuration for all database settings
- Connection pooling and retry logic required

**Protocol Support**:
- REST API, gRPC, HTTP/1.1, HTTP/2, HTTP/3 support
- Environment variables for protocol configuration
- Multi-protocol implementation required

**Performance Optimization (Python):**
- Dataclasses with slots mandatory (30-50% memory reduction)
- Type hints required for all Python code
- asyncio for I/O-bound operations
- threading for blocking I/O
- multiprocessing for CPU-bound operations
- Avoid premature optimization - profile first

**High-Performance Networking (Case-by-Case):**
- XDP (eXpress Data Path): Kernel-level packet processing
- AF_XDP: Zero-copy socket for user-space packet processing
- Use only for network-intensive applications requiring >100K packets/sec
- Evaluate Python vs Go based on traffic requirements

**Microservices Architecture**:
- Web UI, API, and Connector as **separate containers by default**
- Single responsibility per service
- API-first design
- Independent deployment and scaling
- Each service has its own Dockerfile and dependencies

**Docker Standards**:
- Multi-arch builds (amd64/arm64)
- Debian-slim base images
- Docker Compose for local development
- Minimal host port exposure

**Testing**:
- Unit tests: Network isolated, mocked dependencies
- Integration tests: Component interactions
- E2E tests: Critical workflows
- Performance tests: Scalability validation

**Security**:
- TLS 1.2+ required
- Input validation mandatory
- JWT, MFA, mTLS standard
- SSO as enterprise feature

## Application Architecture

**ALWAYS use microservices architecture** - decompose into specialized, independently deployable containers:

1. **Web UI Container**: ReactJS frontend (separate container, served via nginx)
2. **Application API Container**: Flask + Flask-Security-Too backend (separate container)
3. **Connector Container**: External system integration (separate container)

**Default Container Separation**: Web UI and API are ALWAYS separate containers by default. This provides:
- Independent scaling of frontend and backend
- Different resource allocation per service
- Separate deployment lifecycles
- Technology-specific optimization

**Benefits**:
- Independent scaling
- Technology diversity
- Team autonomy
- Resilience
- Continuous deployment

📚 **Detailed Architecture Patterns**: See [Development Standards - Microservices Architecture](docs/STANDARDS.md#microservices-architecture)

## Common Integration Patterns

### Quart + JWT Auth + PyDAL
```python
from quart import Quart, jsonify, request
from quart_cors import cors
from pydal import DAL, Field
from dataclasses import dataclass
from typing import Optional
import jwt

app = Quart(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app = cors(app)

# PyDAL database connection
db = DAL(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
    pool_size=10
)

# Define tables with PyDAL
db.define_table('users',
    Field('email', 'string', unique=True),
    Field('password', 'string'),
    Field('active', 'boolean', default=True),
    migrate=True)

# Async endpoint with JWT validation
@app.route('/api/v1/protected', methods=['GET'])
async def protected_resource():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Missing token'}), 401
    token = auth.split(' ')[1]
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    return jsonify({'message': 'This is a protected endpoint'})

@app.route('/healthz', methods=['GET'])
async def health():
    return jsonify({'status': 'healthy'}), 200
```

### Hybrid Database Approach: SQLAlchemy Initialization + PyDAL Day-to-Day

The killkrill project uses a hybrid database strategy:
- **Initialization Phase**: SQLAlchemy for schema design, migrations, and complex setup operations
- **Runtime Operations**: PyDAL for daily CRUD operations and business logic

**Rationale**:
- SQLAlchemy provides robust schema versioning and migration capabilities
- PyDAL offers simpler syntax and better multi-database abstraction for routine operations
- Clear separation of concerns between setup (SQLAlchemy) and operations (PyDAL)

**Setup Example (SQLAlchemy)**:
```python
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from alembic import op
import sqlalchemy as sa

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    active = Column(Boolean, default=True)
```

### Database Integration (PyDAL with Multi-Database Support - Day-to-Day Operations)
```python
from pydal import DAL, Field
from dataclasses import dataclass
import os

# Valid DB_TYPE values for input validation (postgres, mysql, sqlite only)
VALID_DB_TYPES = {
    'postgres', 'mysql', 'sqlite'
}

@dataclass(slots=True, frozen=True)
class UserModel:
    """User model with slots for memory efficiency"""
    id: int
    email: str
    name: str
    active: bool

def get_db_connection() -> DAL:
    """Initialize PyDAL with environment variables and multi-DB support"""
    db_type = os.getenv('DB_TYPE', 'postgres')

    # Input validation - ensure DB_TYPE matches PyDAL expectations
    if db_type not in VALID_DB_TYPES:
        raise ValueError(f"Invalid DB_TYPE: {db_type}. Must be one of: {VALID_DB_TYPES}")

    # Build connection URI
    db_uri = f"{db_type}://" \
             f"{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@" \
             f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/" \
             f"{os.getenv('DB_NAME')}"

    # MariaDB Galera specific settings
    galera_mode = os.getenv('GALERA_MODE', 'false').lower() == 'true'

    dal_kwargs = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', '10')),
        'migrate_enabled': True,
        'check_reserved': ['all'],
        'lazy_tables': True
    }

    # Galera-specific: handle wsrep_sync_wait for read-your-writes consistency
    if galera_mode and db_type == 'mysql':
        dal_kwargs['driver_args'] = {'init_command': 'SET wsrep_sync_wait=1'}

    return DAL(db_uri, **dal_kwargs)
```

### ReactJS Frontend Integration
```javascript
// API client for Quart backend
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add JWT token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Protected component example
import React, { useEffect, useState } from 'react';

function ProtectedComponent() {
  const [data, setData] = useState(null);

  useEffect(() => {
    apiClient.get('/api/v1/protected')
      .then(response => setData(response.data))
      .catch(error => console.error('Error:', error));
  }, []);

  return <div>{data?.message}</div>;
}
```

### License-Gated Features (Python)
```python
from shared.licensing import license_client, requires_feature

@app.route('/api/v1/advanced/analytics', methods=['GET'])
@requires_feature("advanced_analytics")
async def generate_advanced_report():
    """Requires authentication AND professional+ license"""
    return jsonify({'report': await analytics.generate_report()})
```

### Monitoring Integration
```python
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.route('/metrics', methods=['GET'])
async def metrics():
    return await app.response_class(
        generate_latest(),
        mimetype='text/plain; charset=utf-8'
    )
```

### Multi-Service Log/Metrics Processing Patterns

Killkrill's distributed architecture processes high-volume log and metrics data across specialized services. This section documents critical integration patterns for multi-service data pipelines.

**Log Processing Pipeline Architecture**:
```
[Log Receiver] → [Redis Queue] → [Log Worker] → [PostgreSQL]
  (syslog/HTTP)    (async)      (parsing)      (storage)
  100K+ msg/sec    buffering    filtering      persistence
```

**Log Ingestion Pattern**:
- Receiver service: Flask endpoint accepts POST requests with log batches
- Queue storage: Redis list for async processing (`log_queue`)
- Worker service: Async consumer pulls from queue, processes, persists to PostgreSQL
- Database: PyDAL table with timestamp, level, message, source fields

**Metrics Pipeline** (aggregation pattern):
```
[Metrics Receiver] → [Redis Queue] → [Metrics Worker] → [Time-Series DB]
(Prometheus/HTTP)   (batching)      (aggregation)      (PostgreSQL)
 100K+ events/sec   windowed        rolling avg        persistence
```

**Metrics Aggregation Pattern**:
- Worker service: Consumes metrics from Redis queue
- In-memory buffering: Aggregates stats (sum, min, max, avg) per metric
- Periodic flush: Writes aggregated results to PostgreSQL time-series table
- Batching: Flushes when buffer reaches threshold (e.g., 100 metrics)

**API Query Pattern**:
- API service queries aggregated metrics and logs from PostgreSQL
- Endpoints: `/api/v1/metrics?name=...` and `/api/v1/logs?level=...&source=...`
- Pagination: LIMIT/OFFSET for large result sets
- Indexing: Create indexes on frequently queried columns (metric_name, level, source)

**Key Patterns**: Async processing via Redis queues, in-memory batching before persistence, windowed aggregation for statistics, backpressure handling, exponential backoff retries, centralized PostgreSQL queries, UTC timestamps for correlation, JSON structured logging

## Website Integration Requirements

**Killkrill Deployment MUST include two integrated websites**:
1. **Marketing/Sales Website** (Node.js + React, separately hosted)
2. **Documentation Website** (Auto-generated from Markdown docs/)

**Website Design**: Modern, responsive (mobile/tablet/desktop), subtle gradients, <2s load times, clear navigation, PenguinTech branding

**Documentation Features**: API docs with examples, deployment guides (Docker/K8s/Helm), environment variables, architecture diagrams, log/metrics pipelines, FAQ, license integration, support info

**Marketing Features**: Product overview, architecture/data flow, performance benchmarks, customer case studies, pricing, trial options

**Repository Setup**:
- Add `github.com/penguintechinc/website` as sparse checkout submodule
- Create Killkrill-specific folders: `killkrill/` and `killkrill-docs/`
- Marketing site in `killkrill/` (Node.js + React)
- Documentation in `killkrill-docs/` (Markdown source, auto-generated HTML)

**Essential Content**: Product features, architecture overview, API docs, K8s/Helm deployment, env vars, log/metrics setup, monitoring config, performance tuning, troubleshooting, license/enterprise options

## Troubleshooting & Support

### Common Issues
1. **Port Conflicts**: Check docker-compose port mappings
2. **Database Connections**: Verify connection strings and permissions
3. **License Validation Failures**: Check license key format and network connectivity
4. **Build Failures**: Check dependency versions and compatibility
5. **Test Failures**: Review test environment setup

### Debug Commands
```bash
# Container debugging
docker-compose logs -f service-name
docker exec -it container-name /bin/bash

# Application debugging
make debug                    # Start with debug flags
make logs                     # View application logs
make health                   # Check service health

# License debugging
make license-debug            # Test license server connectivity
make license-validate         # Validate current license
```

### Support Resources
- **Technical Documentation**: [Development Standards](docs/STANDARDS.md)
- **License Integration**: [License Server Guide](docs/licensing/license-server-integration.md)
- **Integration Support**: support@penguintech.io
- **Sales Inquiries**: sales@penguintech.io
- **License Server Status**: https://status.penguintech.io

## CI/CD & Workflows

### Documentation
- **Complete workflow documentation**: See [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)
- **CI/CD standards and requirements**: See [`docs/STANDARDS.md`](docs/STANDARDS.md)

### Build Naming Conventions

All container images follow automatic naming based on branch and version changes:

| Scenario | Main Branch | Other Branches |
|----------|------------|-----------------|
| Regular build (no `.version` change) | `beta-<epoch64>` | `alpha-<epoch64>` |
| Version release (`.version` changed) | `vX.X.X-beta` | `vX.X.X-alpha` |
| Tagged release | `vX.X.X` + `latest` | N/A |

**Example**: Updating `.version` to `1.2.0` on main branch triggers builds tagged `v1.2.0-beta` (and auto-creates a GitHub pre-release).

### Version Management

- **Location**: `.version` file in repository root
- **Format**: Semantic versioning (e.g., `1.2.3`)
- **File tracking**: All workflows monitor `.version` for changes
- **Update command**: Edit `.version` file and commit
  ```bash
  echo "1.2.3" > .version
  git add .version
  git commit -m "Release v1.2.3"
  ```

### Pre-Commit Checklist

Before committing, run in this order:

- [ ] **Linters**: `npm run lint` or `golangci-lint run` or equivalent
- [ ] **Security scans**: `npm audit`, `gosec`, `bandit` (per language)
- [ ] **Tests**: `npm test`, `go test ./...`, `pytest` (unit tests only)
- [ ] **Version updates**: Update `.version` if releasing new version
- [ ] **Documentation**: Update docs if adding/changing workflows
- [ ] **No secrets**: Verify no credentials, API keys, or tokens in code
- [ ] **Docker builds**: Verify Dockerfile uses debian-slim base (no alpine)

**Only commit when asked** — follow the pre-commit checklist above, then wait for approval before `git commit`.

### Full Documentation

For complete workflow behavior, troubleshooting, and project-specific details, see [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md).

## Template Customization

### Adding New Data Processors/Workers

When extending Killkrill with new data processing pipelines:

1. Create service directory following existing patterns: `apps/newtype-worker/`
2. Implement Receiver if high-throughput ingestion needed (Flask endpoint)
3. Implement Worker with async Redis queue consumption
4. Define PyDAL tables for processed data persistence
5. Use Python 3.12+ with dataclasses for memory efficiency
6. Add unit tests with mocked Redis/database
7. Update architecture diagrams and API documentation
8. Create Helm chart for Kubernetes deployment

### Adding New API Endpoints

Extend the Go API service: Add handler in `apps/api/handlers/`, use `/api/v1/` versioning, validate inputs, query PostgreSQL, add tests, update documentation.

### Adding New Language Services

For non-standard languages: Create `apps/newservice/` with Dockerfile, add language linting, CI/CD workflow, PostgreSQL integration, Prometheus metrics, Trivy scanning, and documentation.

### Enterprise Integration Customization

For enterprise deployments:

1. **License Server**: Check on startup, gate features, set `RELEASE_MODE=true`
2. **Multi-Tenancy**: Schema per tenant, include tenant ID in all data, scope queries
3. **Usage Tracking**: Log API calls, track ingestion volumes per tenant, report to license server
4. **Audit Logging**: Record user actions with timestamp, action, resource, result
5. **Enterprise Monitoring**: Prometheus + Grafana, alerting for SLA violations, usage reports
6. **High Availability**: K8s replicas for workers, StatefulSets for stateful services, load balancing

## License & Legal

**License File**: `LICENSE.md` (located at project root)

**License Type**: Limited AGPL-3.0 with commercial use restrictions and Contributor Employer Exception

The `LICENSE.md` file is located at the project root following industry standards.

**Template Version**: 1.3.0
**Last Updated**: 2025-12-03
**Maintained by**: Penguin Tech Inc
**License Server**: https://license.penguintech.io

**Key Updates in v1.3.0:**
- Three-container architecture: Flask backend, Go backend, WebUI shell
- WebUI shell with Node.js + React, role-based access (Admin, Maintainer, Viewer)
- Flask backend with PyDAL, JWT auth, user management
- Go backend with XDP/AF_XDP support, NUMA-aware memory pools
- GitHub Actions workflows for multi-arch builds (AMD64, ARM64)
- Gold text theme by default, Elder sidebar pattern, WaddlePerf tabs
- Docker Compose updated for new architecture

**Key Updates in v1.2.0:**
- Web UI and API as separate containers by default
- Mandatory linting for all languages (flake8, ansible-lint, eslint, etc.)
- CodeQL inspection compliance required
- Multi-database support by design (all PyDAL databases + MariaDB Galera)
- DB_TYPE environment variable with input validation
- Flask as sole web framework (PyDAL for database abstraction)

**Key Updates in v1.1.0:**
- Flask-Security-Too mandatory for authentication
- ReactJS as standard frontend framework
- Python 3.13 vs Go decision criteria
- XDP/AF_XDP guidance for high-performance networking
- WaddleAI integration patterns
- Release-mode license enforcement
- Performance optimization requirements (dataclasses with slots)

*This template provides a production-ready foundation for enterprise software development with comprehensive tooling, security, operational capabilities, and integrated licensing management.*
