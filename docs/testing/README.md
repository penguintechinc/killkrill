# Testing Strategy & Overview

Killkrill's multi-service architecture requires comprehensive testing across unit, integration, and end-to-end levels. This directory contains detailed documentation for all testing patterns, frameworks, and best practices.

## Test Levels & Categories

| Level           | Purpose                              | Speed    | Coverage          | Markers                    |
| --------------- | ------------------------------------ | -------- | ----------------- | -------------------------- |
| **Unit**        | Isolated function testing with mocks | <1 min   | Logic, validation | `@pytest.mark.unit`        |
| **API**         | HTTP endpoint verification           | <2 min   | Request/response  | `@pytest.mark.api`         |
| **Integration** | Component interactions with services | 2-5 min  | Data flows        | `@pytest.mark.integration` |
| **E2E**         | Complete pipeline workflows          | 5-10 min | Full system       | `@pytest.mark.e2e`         |
| **Load**        | Throughput & performance             | 5-15 min | Scalability       | `@pytest.mark.load`        |
| **Security**    | Auth, encryption, validation         | 2-5 min  | Safety            | `@pytest.mark.security`    |

## Quick Start

### Running Tests

```bash
# All tests
make test

# By category
make test-unit              # Fast unit tests only
make test-api               # API endpoint tests
make test-integration       # Integration tests
make test-e2e               # End-to-end workflows
make test-security          # Security validation
make test-performance       # Load & performance

# With coverage
pytest --cov=services tests/unit/

# Specific service
pytest tests/unit/log-worker/
pytest tests/integration/metrics-worker/

# By marker
pytest -m "unit and not slow"
pytest -m "integration"
```

### Test File Organization

```
tests/
├── conftest.py                    # Global fixtures
├── pytest.ini                     # Configuration
├── unit/                          # Fast unit tests (mocked)
│   ├── conftest.py               # Unit-level fixtures
│   ├── shared/
│   ├── log-worker/
│   ├── metrics-worker/
│   ├── receivers/
│   └── manager/
├── api/                           # HTTP endpoint tests
│   ├── conftest.py
│   ├── flask-backend/
│   └── go-backend/
├── integration/                   # Real service tests
│   ├── conftest.py               # DB/Redis/ES fixtures
│   ├── log-worker/
│   ├── metrics-worker/
│   ├── receivers/
│   └── pipelines/
├── e2e/                          # End-to-end workflows
│   ├── conftest.py               # Full stack fixtures
│   ├── test_user_workflows.py
│   ├── test_log_pipeline.py
│   └── test_metrics_pipeline.py
└── performance/                   # Load tests
    ├── test_throughput.py
    └── test_latency.py
```

## Key Testing Patterns

### 1. Pytest Markers

All tests use markers for categorization:

```python
@pytest.mark.unit
def test_log_parsing():
    """Fast isolated test with mocks"""
    pass

@pytest.mark.integration
@pytest.mark.requires_db
def test_database_persistence():
    """Real database connection"""
    pass

@pytest.mark.e2e
@pytest.mark.slow
def test_complete_pipeline():
    """Full system workflow"""
    pass

@pytest.mark.security
def test_authentication():
    """Security validation"""
    pass
```

### 2. Fixtures & Dependency Injection

Define fixtures in `conftest.py` at appropriate levels:

```python
# tests/conftest.py (global)
@pytest.fixture
def app():
    """Flask application instance"""
    app = create_app('testing')
    return app

# tests/unit/conftest.py (unit-level)
@pytest.fixture
def mock_redis():
    """Mocked Redis client"""
    return MagicMock()

# tests/integration/conftest.py (integration-level)
@pytest.fixture
def redis_client():
    """Real Redis test instance"""
    client = redis.Redis(db=15)  # Use separate DB for tests
    yield client
    client.flushdb()
```

### 3. Async Testing

For async code, use pytest-asyncio:

```python
@pytest.mark.asyncio
async def test_async_worker():
    """Test async functions"""
    result = await process_logs()
    assert result is not None
```

### 4. Parametrization

Test multiple inputs efficiently:

```python
@pytest.mark.parametrize("log_level,expected", [
    ("info", "INFO"),
    ("warn", "WARNING"),
    ("error", "ERROR"),
    ("debug", "DEBUG"),
])
def test_log_level_mapping(log_level, expected):
    """Test all log levels"""
    assert map_level(log_level) == expected
```

## Coverage Requirements

- **Unit tests**: ≥85% coverage
- **Integration tests**: ≥75% coverage combined with unit
- **E2E tests**: Critical paths only
- **Overall target**: ≥80% combined

```bash
# Generate coverage report
pytest --cov=services --cov-report=html tests/

# View report
open htmlcov/index.html
```

## Before Every Commit

1. **Linting** → `flake8`, `black`, `isort`
2. **Security** → `bandit`, `safety check`
3. **Unit tests** → `pytest -m unit`
4. **No test failures** → All marked tests pass

## CI/CD Integration

Tests run automatically in GitHub Actions:

- **Pull Requests**: Unit + API tests (fast feedback)
- **Main Branch**: All tests including E2E
- **Releases**: Full suite + coverage verification

See [WORKFLOWS.md](../WORKFLOWS.md) for complete CI/CD details.

## Documentation Files

- [Unit Tests](unit-tests.md) - Testing isolated functions with mocks
- [Integration Tests](integration-tests.md) - Testing with real services
- [E2E Tests](e2e-tests.md) - Testing complete workflows
- [Worker Tests](worker-tests.md) - Worker-specific patterns

## Common Issues & Solutions

| Issue                             | Solution                                                         |
| --------------------------------- | ---------------------------------------------------------------- |
| Tests fail locally but pass in CI | Check Python version, dependencies, env vars                     |
| Flaky tests                       | Use proper waits/retries, avoid hardcoded timeouts               |
| Slow tests                        | Check for unnecessary sleeps, use mocks instead of real services |
| Import errors                     | Ensure app is installed: `pip install -e .`                      |
| DB locked errors                  | Use separate test DB (redis db=15, MySQL test prefix)            |

## Performance Benchmarks

Expected test execution times:

- Unit tests: <60 seconds (all)
- API tests: <120 seconds (all)
- Integration tests: 2-5 minutes
- E2E tests: 5-10 minutes
- Full suite: <20 minutes

---

**Last Updated**: 2026-01-07
**Framework**: Pytest 7.0+, Python 3.12+
