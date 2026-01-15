# Integration Testing Guide

Integration tests verify that components work correctly together with real external services (databases, Redis, Elasticsearch, etc.) without mocking. They test data flow between services.

## Goals & Requirements

- **Real Services**: Use actual Redis, PostgreSQL, Elasticsearch test instances
- **Data Flow**: Verify complete processing from input to storage
- **No Mocks**: All external services are real (not mocked)
- **Isolated Data**: Use separate test DBs, clean before/after each test
- **Medium Speed**: 2-5 minutes total
- **Coverage**: ≥75% of data processing logic

## Test Structure

### File Organization

```
tests/integration/
├── conftest.py                     # Shared fixtures (DB, Redis, ES)
├── log-worker/
│   ├── test_redis_consumption.py
│   ├── test_elasticsearch_output.py
│   ├── test_error_handling.py
│   └── test_transformation.py
├── metrics-worker/
│   ├── test_redis_consumption.py
│   ├── test_metrics_aggregation.py
│   ├── test_prometheus_output.py
│   └── test_error_handling.py
├── receivers/
│   ├── test_log_ingestion.py
│   ├── test_metrics_ingestion.py
│   ├── test_syslog_ingestion.py
│   └── test_validation.py
└── pipelines/
    ├── test_log_pipeline.py
    ├── test_metrics_pipeline.py
    └── test_error_recovery.py
```

## Fixtures & Service Setup

### Shared Fixtures (conftest.py)

```python
import pytest
import redis
import psycopg2
from elasticsearch import Elasticsearch
from datetime import datetime

@pytest.fixture(scope='session')
def redis_url():
    """Redis URL from environment"""
    return os.getenv('REDIS_URL', 'redis://localhost:6379/1')

@pytest.fixture(scope='session')
def postgres_url():
    """PostgreSQL URL for test database"""
    return os.getenv('TEST_DATABASE_URL',
        'postgresql://test:test@localhost/killkrill_test')

@pytest.fixture(scope='session')
def elasticsearch_url():
    """Elasticsearch URL for test instance"""
    return os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')

@pytest.fixture
def redis_client(redis_url):
    """Fresh Redis client for each test"""
    client = redis.from_url(redis_url)
    yield client
    # Cleanup - delete test streams
    client.delete('logs-stream', 'metrics-stream')

@pytest.fixture
def postgres_connection(postgres_url):
    """PostgreSQL test connection"""
    conn = psycopg2.connect(postgres_url)
    yield conn
    conn.close()

@pytest.fixture
def elasticsearch_client(elasticsearch_url):
    """Elasticsearch client for test instance"""
    client = Elasticsearch([elasticsearch_url])
    yield client
    # Cleanup - delete test indices
    client.indices.delete(index='logs-test-*', ignore_missing=True)
    client.indices.delete(index='metrics-test-*', ignore_missing=True)

@pytest.fixture
def db_session(postgres_url):
    """SQLAlchemy session for integration tests"""
    from shared.models import create_engine
    engine = create_engine(postgres_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
```

### Service Configuration Fixtures

```python
@pytest.fixture
def log_worker_config(redis_client):
    """Configure log worker for testing"""
    return {
        'redis_url': redis_client.connection_pool.connection_kwargs['host'],
        'redis_port': redis_client.connection_pool.connection_kwargs['port'],
        'redis_db': redis_client.connection_pool.connection_kwargs['db'],
        'elasticsearch_url': 'http://localhost:9200',
        'elasticsearch_index': 'logs-test',
        'batch_size': 10,
        'timeout': 5,
    }

@pytest.fixture
def log_worker(log_worker_config):
    """Instantiate log worker with test config"""
    from log_worker.worker import LogWorker
    return LogWorker(log_worker_config)
```

## Common Integration Test Patterns

### 1. Redis Queue Consumption

```python
import json
import pytest

@pytest.mark.integration
@pytest.mark.requires_db
def test_log_worker_consumes_from_redis_stream(redis_client, log_worker):
    """Worker should consume logs from Redis Stream"""
    # Setup: Add test log to stream
    test_log = {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "api",
        "level": "info",
        "message": "Test log entry"
    }
    redis_client.xadd('logs-stream', {'data': json.dumps(test_log)})

    # Execute: Worker processes stream
    log_worker.process_batch(count=1)

    # Verify: Stream is consumed
    remaining = redis_client.xlen('logs-stream')
    assert remaining == 0

@pytest.mark.integration
def test_worker_handles_malformed_logs(redis_client, log_worker):
    """Worker should handle invalid logs gracefully"""
    # Add invalid log (missing required fields)
    redis_client.xadd('logs-stream', {'data': '{"invalid": "log"}'})

    # Should not crash
    with pytest.raises(LogParseError):
        log_worker.process_batch(count=1)
```

### 2. Database Persistence

```python
@pytest.mark.integration
@pytest.mark.requires_db
def test_logs_persisted_to_elasticsearch(redis_client, elasticsearch_client, log_worker):
    """Logs should be indexed in Elasticsearch after processing"""
    # Setup: Add log to Redis stream
    test_log = {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "auth-service",
        "level": "error",
        "message": "Authentication failed"
    }
    redis_client.xadd('logs-stream', {'data': json.dumps(test_log)})

    # Execute: Process logs
    log_worker.process_batch(count=1)

    # Verify: Log indexed in Elasticsearch
    time.sleep(1)  # Allow indexing
    search_result = elasticsearch_client.search(
        index='logs-*',
        query={"match": {"service": "auth-service"}}
    )

    assert search_result['hits']['total']['value'] > 0
    log_doc = search_result['hits']['hits'][0]['_source']
    assert log_doc['message'] == "Authentication failed"

@pytest.mark.integration
def test_metrics_aggregated_in_database(redis_client, db_session, metrics_worker):
    """Metrics should be aggregated and stored in database"""
    # Setup: Add metrics to Redis stream
    for i in range(5):
        metric = {
            "name": "http_requests_total",
            "value": 100 + i,
            "labels": {"endpoint": "/api/v1/users"},
            "timestamp": int(time.time())
        }
        redis_client.xadd('metrics-stream', {'data': json.dumps(metric)})

    # Execute: Worker aggregates metrics
    metrics_worker.aggregate_batch()

    # Verify: Aggregated metric in database
    from shared.models import AggregatedMetric
    agg = db_session.query(AggregatedMetric).filter_by(
        name='http_requests_total'
    ).first()

    assert agg is not None
    assert agg.count == 5
    assert agg.sum == 502  # 100+101+102+103+104
```

### 3. Error Handling & Recovery

```python
@pytest.mark.integration
def test_worker_retries_on_elasticsearch_timeout(redis_client, elasticsearch_client,
                                                   log_worker, mocker):
    """Worker should retry on temporary service failures"""
    # Setup: Mock Elasticsearch to fail once
    call_count = {'count': 0}

    original_bulk = elasticsearch_client.bulk

    def mock_bulk(*args, **kwargs):
        call_count['count'] += 1
        if call_count['count'] == 1:
            raise TimeoutError("Connection timeout")
        return original_bulk(*args, **kwargs)

    mocker.patch.object(elasticsearch_client, 'bulk', side_effect=mock_bulk)

    # Add test log
    test_log = {"timestamp": "2024-01-06T12:00:00Z", "service": "api", ...}
    redis_client.xadd('logs-stream', {'data': json.dumps(test_log)})

    # Execute: Should retry and succeed
    log_worker.process_batch(count=1, max_retries=2)

    # Verify: Called at least twice (initial + retry)
    assert call_count['count'] >= 2

@pytest.mark.integration
def test_worker_handles_partial_failures(redis_client, log_worker):
    """Worker should handle partial batch failures gracefully"""
    # Setup: Mix of valid and invalid logs
    logs = [
        {"timestamp": "2024-01-06T12:00:00Z", "service": "api", "level": "info", "message": "valid"},
        {"invalid": "log"},  # Invalid
        {"timestamp": "2024-01-06T12:00:02Z", "service": "api", "level": "error", "message": "valid"},
    ]

    for log in logs:
        redis_client.xadd('logs-stream', {'data': json.dumps(log)})

    # Execute: Process all logs
    results = log_worker.process_batch(count=3, stop_on_error=False)

    # Verify: 2 succeeded, 1 failed
    assert results['success'] == 2
    assert results['failed'] == 1
```

### 4. Data Transformation Validation

```python
@pytest.mark.integration
def test_log_enrichment_in_pipeline(redis_client, elasticsearch_client, log_worker):
    """Worker should enrich logs with additional fields"""
    # Setup: Raw log entry
    test_log = {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "api",
        "level": "info",
        "message": "Request completed"
    }
    redis_client.xadd('logs-stream', {'data': json.dumps(test_log)})

    # Execute: Process log
    log_worker.process_batch(count=1)

    # Verify: Enriched fields in Elasticsearch
    time.sleep(1)
    search_result = elasticsearch_client.search(
        index='logs-*',
        query={"match": {"message": "Request completed"}}
    )

    doc = search_result['hits']['hits'][0]['_source']
    assert 'processed_at' in doc  # Added by worker
    assert 'environment' in doc    # Added by worker
    assert 'version' in doc        # Added by worker
```

### 5. Concurrency & Load

```python
@pytest.mark.integration
@pytest.mark.slow
def test_worker_processes_large_batch(redis_client, elasticsearch_client, log_worker):
    """Worker should handle large batches without data loss"""
    # Setup: Add 1000 logs to stream
    num_logs = 1000
    for i in range(num_logs):
        log = {
            "timestamp": f"2024-01-06T12:00:{i%60:02d}Z",
            "service": f"service-{i % 10}",
            "level": ["info", "warn", "error"][i % 3],
            "message": f"Log message {i}"
        }
        redis_client.xadd('logs-stream', {'data': json.dumps(log)})

    # Execute: Process all logs
    log_worker.process_batch(count=num_logs)

    # Verify: All logs indexed
    time.sleep(2)
    search_result = elasticsearch_client.search(
        index='logs-*',
        query={"match_all": {}},
        size=0
    )

    assert search_result['hits']['total']['value'] == num_logs

@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_worker_concurrent_processing(redis_client, metrics_worker):
    """Metrics worker should handle concurrent streams"""
    # Setup: Add to multiple metric streams
    streams = ['http_requests', 'db_queries', 'cache_hits']

    for stream in streams:
        for i in range(100):
            metric = {
                "name": stream,
                "value": i,
                "timestamp": int(time.time())
            }
            redis_client.xadd(f"{stream}-stream", {'data': json.dumps(metric)})

    # Execute: Process concurrently
    tasks = [metrics_worker.process_stream_async(s) for s in streams]
    results = await asyncio.gather(*tasks)

    # Verify: All streams processed
    assert all(r.success for r in results)
```

## Testing Checklist

Before committing integration tests:

- [ ] All fixtures properly cleanup after tests
- [ ] Tests don't depend on execution order
- [ ] Database/Redis isolated from other tests
- [ ] Error cases tested
- [ ] Timeout/retry logic tested
- [ ] Data validation verified
- [ ] Performance acceptable (<5 min total)
- [ ] No hardcoded test data paths
- [ ] Environment variables used for service URLs

## Best Practices

1. **Isolation**: Each test should be independent

   ```python
   # Good - cleanup after each test
   @pytest.fixture
   def redis_client(redis_url):
       client = redis.from_url(redis_url)
       yield client
       client.flushdb()  # Clean up

   # Bad - shared state between tests
   redis_client = redis.Redis()
   ```

2. **Realistic Data**: Use production-like test data

   ```python
   # Good - realistic metrics
   metric = {
       "name": "http_request_duration_seconds",
       "value": 0.125,
       "labels": {"method": "GET", "endpoint": "/api/v1/users"},
   }

   # Bad - oversimplified
   metric = {"name": "metric", "value": 1}
   ```

3. **Waits & Retries**: Use proper waits for async operations

   ```python
   # Good - explicit wait
   elasticsearch_client.indices.refresh(index='logs-*')
   result = elasticsearch_client.search(index='logs-*', ...)

   # Bad - arbitrary sleep
   time.sleep(5)
   result = elasticsearch_client.search(index='logs-*', ...)
   ```

4. **Environment Variables**: Use env vars for service URLs

   ```python
   # Good
   @pytest.fixture
   def elasticsearch_url():
       return os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')

   # Bad - hardcoded
   elasticsearch_url = 'http://localhost:9200'
   ```

---

**Last Updated**: 2026-01-07
**Scope**: Real services, data flow validation, 2-5 minute suite
