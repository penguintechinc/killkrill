# End-to-End Testing Guide

End-to-end tests verify complete workflows from user input through all services to final output. They test the full application stack together.

## Goals & Requirements

- **Complete Workflows**: User action → HTTP → API → Worker → Storage → Query result
- **Real Services**: All services running (API, receivers, workers, databases)
- **Realistic Scenarios**: Mimic production user workflows
- **Longer Execution**: 5-10 minutes typical
- **Critical Path Coverage**: Test main happy paths and critical errors only

## Test Structure

### File Organization

```
tests/e2e/
├── conftest.py                      # Full stack fixtures
├── test_user_workflows.py            # User-centric scenarios
├── test_log_pipeline.py              # Complete log flow
├── test_metrics_pipeline.py          # Complete metrics flow
└── test_error_scenarios.py           # System failure handling
```

### Service Requirements

E2E tests require all services running:

```bash
# Start full stack
docker-compose -f docker-compose.test.yml up

# Services that must be healthy:
# - Log Receiver (Flask) on port 8081
# - Metrics Receiver (Flask) on port 8082
# - API (Go) on port 8080
# - Log Worker (Python background)
# - Metrics Worker (Python background)
# - Redis on port 6379
# - PostgreSQL on port 5432
# - Elasticsearch on port 9200
```

## E2E Test Patterns

### 1. Complete User Workflows

```python
import pytest
import requests
import time
from datetime import datetime

@pytest.mark.e2e
class TestUserWorkflows:
    """Complete workflows from user perspective"""

    def test_user_sends_log_and_queries_it(self, api_client):
        """User sends log → system processes → user queries result"""
        # Step 1: User sends log via HTTP
        auth_token = "PENG-TEST-TEST-TEST-TEST-TEST"
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "e2e-test",
            "level": "info",
            "message": "User workflow test log"
        }

        response = api_client.post(
            '/api/v1/logs',
            json=log_data,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 202  # Accepted for async processing

        # Step 2: Wait for processing
        time.sleep(2)  # Allow worker to consume and index

        # Step 3: User queries their log
        query_response = api_client.get(
            '/api/v1/logs?service=e2e-test',
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert query_response.status_code == 200
        logs = query_response.json()['data']
        assert len(logs) > 0
        assert logs[0]['message'] == "User workflow test log"

    def test_user_sends_metrics_and_views_dashboard(self, api_client):
        """User sends metrics → system aggregates → dashboard shows data"""
        # Step 1: Send multiple metric points
        auth_token = "PENG-TEST-TEST-TEST-TEST-TEST"
        for i in range(5):
            metric = {
                "name": "api_requests_total",
                "value": 100 + i,
                "labels": {"endpoint": "/users", "method": "GET"},
                "timestamp": int(time.time())
            }

            response = api_client.post(
                '/api/v1/metrics',
                json=metric,
                headers={'Authorization': f'Bearer {auth_token}'}
            )
            assert response.status_code == 202

        # Step 2: Wait for aggregation
        time.sleep(3)

        # Step 3: Query aggregated metrics
        agg_response = api_client.get(
            '/api/v1/metrics/aggregate?name=api_requests_total',
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert agg_response.status_code == 200
        agg_data = agg_response.json()['data']
        assert agg_data['count'] == 5
        assert agg_data['sum'] == 502  # 100+101+102+103+104
```

### 2. Log Ingestion Pipeline

```python
@pytest.mark.e2e
class TestLogPipeline:
    """Complete log ingestion pipeline: HTTP → Redis → Worker → Elasticsearch"""

    def test_http_log_ingestion_end_to_end(self, api_client, elasticsearch_client):
        """Log sent via HTTP should appear in Elasticsearch"""
        log_id = f"e2e-{datetime.utcnow().timestamp()}"

        # Send log
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "webui",
            "level": "info",
            "message": f"Test log {log_id}"
        }

        response = api_client.post(
            '/api/v1/logs',
            json=log,
            headers={'Authorization': f'Bearer PENG-TEST-TEST-TEST-TEST-TEST'}
        )

        assert response.status_code == 202

        # Wait and verify in Elasticsearch
        max_attempts = 10
        for attempt in range(max_attempts):
            time.sleep(1)

            search_result = elasticsearch_client.search(
                index='logs-*',
                query={"match": {"message": log_id}}
            )

            if search_result['hits']['total']['value'] > 0:
                doc = search_result['hits']['hits'][0]['_source']
                assert doc['service'] == 'webui'
                assert doc['level'] == 'info'
                return  # Success

        raise AssertionError(
            f"Log not found in Elasticsearch after {max_attempts} attempts"
        )

    def test_syslog_ingestion_end_to_end(self, elasticsearch_client):
        """Syslog message should be parsed and indexed"""
        import socket

        # Send syslog message
        syslog_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        syslog_msg = f"<14>Jan  6 12:00:00 localhost webui[123]: E2E test syslog"
        syslog_server.sendto(syslog_msg.encode(), ('localhost', 514))
        syslog_server.close()

        # Wait and verify
        time.sleep(2)
        result = elasticsearch_client.search(
            index='logs-*',
            query={"match": {"message": "E2E test syslog"}}
        )

        assert result['hits']['total']['value'] > 0
        doc = result['hits']['hits'][0]['_source']
        assert doc['service'] == 'webui'

    @pytest.mark.parametrize("log_level", ["debug", "info", "warn", "error"])
    def test_all_log_levels_processed(self, api_client, elasticsearch_client, log_level):
        """All log levels should be processed correctly"""
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "test-service",
            "level": log_level,
            "message": f"Test {log_level} message"
        }

        api_client.post('/api/v1/logs', json=log,
                       headers={'Authorization': f'Bearer PENG-TEST-TEST-TEST-TEST-TEST'})

        time.sleep(2)

        # Search for this specific level
        search_result = elasticsearch_client.search(
            index='logs-*',
            query={"term": {"level": log_level.upper()}}
        )

        assert search_result['hits']['total']['value'] > 0
```

### 3. Metrics Pipeline

```python
@pytest.mark.e2e
class TestMetricsPipeline:
    """Complete metrics pipeline: HTTP → Redis → Worker → Storage"""

    def test_prometheus_scrape_end_to_end(self, api_client, redis_client):
        """Prometheus metrics should be scraped and stored"""
        # Step 1: API exposes metrics endpoint
        response = api_client.get('/metrics')
        assert response.status_code == 200
        assert 'http_requests_total' in response.text

        # Step 2: Metrics worker scrapes and processes
        time.sleep(2)

        # Step 3: Verify metrics in storage
        metric_data = redis_client.hgetall('metrics:aggregated')
        assert len(metric_data) > 0

    def test_metrics_aggregation_end_to_end(self, api_client):
        """Multiple metric points should be aggregated"""
        # Send 10 metric points for same name
        for i in range(10):
            metric = {
                "name": "test_metric_counter",
                "value": 100 + i,
                "labels": {"instance": "test"},
                "timestamp": int(time.time())
            }

            api_client.post(
                '/api/v1/metrics',
                json=metric,
                headers={'Authorization': f'Bearer PENG-TEST-TEST-TEST-TEST-TEST'}
            )

        time.sleep(3)

        # Query aggregated result
        response = api_client.get(
            '/api/v1/metrics/aggregate?name=test_metric_counter',
            headers={'Authorization': f'Bearer PENG-TEST-TEST-TEST-TEST-TEST'}
        )

        assert response.status_code == 200
        data = response.json()['data']
        assert data['count'] == 10
```

### 4. Error & Failure Scenarios

```python
@pytest.mark.e2e
@pytest.mark.slow
class TestErrorScenarios:
    """Test system behavior under failure conditions"""

    def test_missing_authentication_rejected(self, api_client):
        """API should reject requests without authentication"""
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "test",
            "level": "info",
            "message": "Test"
        }

        # No auth token
        response = api_client.post('/api/v1/logs', json=log)
        assert response.status_code in [401, 403]

    def test_invalid_data_rejected(self, api_client):
        """API should validate and reject invalid data"""
        invalid_log = {
            "service": "test"
            # Missing required fields: timestamp, level, message
        }

        response = api_client.post(
            '/api/v1/logs',
            json=invalid_log,
            headers={'Authorization': f'Bearer PENG-TEST-TEST-TEST-TEST-TEST'}
        )

        assert response.status_code == 400
        assert 'error' in response.json() or 'errors' in response.json()

    def test_system_recovers_from_worker_restart(self, api_client, redis_client,
                                                  docker_client):
        """Logs should queue and process after worker restart"""
        # Send logs while worker is healthy
        log_ids = []
        for i in range(5):
            log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "service": "test",
                "level": "info",
                "message": f"Recovery test {i}"
            }

            api_client.post(
                '/api/v1/logs',
                json=log,
                headers={'Authorization': f'Bearer PENG-TEST-TEST-TEST-TEST-TEST'}
            )
            log_ids.append(f"Recovery test {i}")

        # Get queue depth
        queue_depth_before = redis_client.xlen('logs-stream')

        # Restart worker
        docker_client.containers.get('log-worker').restart()

        time.sleep(3)

        # Queue should be consumed after restart
        queue_depth_after = redis_client.xlen('logs-stream')
        assert queue_depth_after < queue_depth_before

    @pytest.mark.requires_network
    def test_graceful_degradation_elasticsearch_down(self, api_client, redis_client,
                                                      elasticsearch_client):
        """System should gracefully handle Elasticsearch downtime"""
        # Send log (should be queued)
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "test",
            "level": "info",
            "message": "ES degradation test"
        }

        response = api_client.post(
            '/api/v1/logs',
            json=log,
            headers={'Authorization': f'Bearer PENG-TEST-TEST-TEST-TEST-TEST'}
        )

        # API should still accept (async processing)
        assert response.status_code == 202

        # Log should remain in queue
        queue_depth = redis_client.xlen('logs-stream')
        assert queue_depth >= 1
```

## E2E Test Fixtures

```python
# tests/e2e/conftest.py

import pytest
import requests
from elasticsearch import Elasticsearch
import redis
import subprocess
import time
import docker

@pytest.fixture(scope='session')
def docker_client():
    """Docker client for container operations"""
    return docker.from_env()

@pytest.fixture(scope='session')
def docker_compose_project(docker_client):
    """Start docker-compose stack"""
    subprocess.run([
        'docker-compose', '-f', 'docker-compose.test.yml', 'up', '-d'
    ], check=True)

    # Wait for services to be ready
    time.sleep(5)

    yield

    # Cleanup
    subprocess.run([
        'docker-compose', '-f', 'docker-compose.test.yml', 'down'
    ], check=True)

@pytest.fixture
def api_client():
    """HTTP client for API requests"""
    class APIClient:
        def __init__(self, base_url='http://localhost:8080'):
            self.base_url = base_url

        def post(self, path, json=None, headers=None):
            url = f"{self.base_url}{path}"
            return requests.post(url, json=json, headers=headers or {})

        def get(self, path, headers=None):
            url = f"{self.base_url}{path}"
            return requests.get(url, headers=headers or {})

    return APIClient()

@pytest.fixture
def elasticsearch_client():
    """Elasticsearch client for verification"""
    return Elasticsearch(['http://localhost:9200'])

@pytest.fixture
def redis_client():
    """Redis client for queue inspection"""
    return redis.Redis(host='localhost', port=6379, db=0)
```

## Execution

```bash
# Run all E2E tests
pytest tests/e2e/ -m e2e

# Run specific E2E test class
pytest tests/e2e/test_log_pipeline.py::TestLogPipeline -m e2e

# Run with verbose output
pytest tests/e2e/ -v -s

# Run and keep services running for debugging
pytest tests/e2e/ --docker-compose-no-cleanup
```

## Best Practices

1. **Use Waits**: Use explicit waits for async operations

   ```python
   # Good
   time.sleep(2)  # Allow worker processing
   result = elasticsearch_client.search(...)

   # Bad - no wait
   result = elasticsearch_client.search(...)
   ```

2. **Test Critical Paths Only**: Don't repeat unit test scenarios

   ```python
   # Good - E2E tests main workflows
   def test_complete_user_workflow():
       send_log() → verify_indexed()

   # Bad - E2E duplicates unit tests
   def test_parse_log_level():  # Should be unit test
       assert parse_level("info") == "INFO"
   ```

3. **Use Unique Identifiers**: Avoid test data collisions

   ```python
   # Good - unique per test run
   log_id = f"e2e-{datetime.utcnow().timestamp()}"
   message = f"Test log {log_id}"

   # Bad - might collide
   message = "Test log"
   ```

4. **Independent Tests**: Tests shouldn't depend on order

   ```python
   # Good - each test is independent
   def test_log_pipeline():
       send_log() → verify()

   # Bad - depends on previous test
   def test_2_verify_logs():
       logs = query_logs()  # Depends on test_1 sending logs
   ```

---

**Last Updated**: 2026-01-07
**Scope**: Full system workflows, 5-10 minute suite
