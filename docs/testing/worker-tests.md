# Worker Service Testing Guide

Comprehensive testing patterns specific to Killkrill's log and metrics worker services, covering async processing, queue consumption, and data transformations.

## Worker Architecture

```
Redis Stream (Input)
        ↓
    ┌───────┐
    │ XREAD │ - Worker reads messages
    └───────┘
        ↓
┌──────────────────┐
│  Message Parser  │ - Parse and validate
└──────────────────┘
        ↓
┌──────────────────┐
│ Transformation   │ - Enrich, normalize
└──────────────────┘
        ↓
┌──────────────────┐
│ Output Handler   │ - Store in ES/DB
└──────────────────┘
        ↓
┌──────────────────┐
│ Acknowledge      │ - XACK message
└──────────────────┘
```

## Testing Levels for Workers

| Level           | Tests                        | Speed    | Real Services |
| --------------- | ---------------------------- | -------- | ------------- |
| **Unit**        | Parse, validate, transform   | <1 min   | None (mocked) |
| **Integration** | Redis → Transform → ES/DB    | 2-5 min  | Redis, ES/DB  |
| **E2E**         | API → Redis → Worker → Query | 5-10 min | Full stack    |

## Unit Tests: Worker Functions

### 1. Log Parsing Tests

```python
import pytest
from log_worker.parser import LogParser, ParseError
from datetime import datetime

@pytest.mark.unit
class TestLogParser:
    """Unit tests for log parsing logic"""

    @pytest.fixture
    def parser(self):
        return LogParser()

    def test_parse_valid_json_log(self, parser):
        """Parse valid JSON log entry"""
        log_json = '''
        {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "info",
            "message": "Request completed",
            "duration_ms": 125
        }
        '''

        result = parser.parse(log_json)

        assert result.timestamp == "2024-01-06T12:00:00Z"
        assert result.service == "api"
        assert result.level == "info"
        assert result.duration_ms == 125

    @pytest.mark.parametrize("missing_field", [
        "timestamp", "service", "level", "message"
    ])
    def test_missing_required_field_raises_error(self, parser, missing_field):
        """Missing required field should raise ParseError"""
        log_data = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "info",
            "message": "Test"
        }
        del log_data[missing_field]

        with pytest.raises(ParseError) as exc:
            parser.parse(str(log_data))

        assert missing_field in str(exc.value).lower()

    def test_parse_syslog_format(self, parser):
        """Parse RFC3164 syslog format"""
        syslog = "<14>Jan  6 12:00:00 host service[123]: User login successful"

        result = parser.parse_syslog(syslog)

        assert result.level == "info"
        assert result.service == "service"
        assert result.pid == "123"
        assert result.message == "User login successful"

    def test_parse_invalid_timestamp_format(self, parser):
        """Invalid ISO8601 timestamp should raise error"""
        log_json = '{"timestamp":"not-a-date","service":"api","level":"info","message":"Test"}'

        with pytest.raises(ParseError):
            parser.parse(log_json)

    def test_parse_future_timestamp_rejected(self, parser):
        """Logs with future timestamps should be rejected"""
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        log_json = f'{{"timestamp":"{future_time}","service":"api","level":"info","message":"Test"}}'

        with pytest.raises(ParseError) as exc:
            parser.parse(log_json, allow_future=False)

        assert "future" in str(exc.value).lower()

    def test_parse_very_old_timestamp_rejected(self, parser):
        """Logs with very old timestamps should be rejected"""
        old_time = (datetime.utcnow() - timedelta(days=365)).isoformat() + "Z"
        log_json = f'{{"timestamp":"{old_time}","service":"api","level":"info","message":"Test"}}'

        with pytest.raises(ParseError):
            parser.parse(log_json, max_age_days=30)
```

### 2. Data Validation Tests

```python
@pytest.mark.unit
class TestLogValidation:
    """Unit tests for log validation rules"""

    @pytest.fixture
    def validator(self):
        from log_worker.validator import LogValidator
        return LogValidator()

    def test_valid_service_names(self, validator):
        """Valid service names should pass"""
        valid_names = ["api", "webui", "log-worker", "auth_service", "Service123"]

        for name in valid_names:
            assert validator.is_valid_service_name(name)

    def test_invalid_service_names_rejected(self, validator):
        """Invalid service names should fail"""
        invalid_names = ["", " ", "service@host", "service/path", "service\x00"]

        for name in invalid_names:
            assert not validator.is_valid_service_name(name)

    def test_message_length_limits(self, validator):
        """Message should respect length limits"""
        # Valid: 1-10000 chars
        assert validator.validate_message("a" * 1)
        assert validator.validate_message("a" * 10000)

        # Invalid: empty or too long
        with pytest.raises(ValueError):
            validator.validate_message("")

        with pytest.raises(ValueError):
            validator.validate_message("a" * 10001)

    def test_log_level_validation(self, validator):
        """Log level should be one of allowed values"""
        valid_levels = ["debug", "info", "warn", "error"]

        for level in valid_levels:
            assert validator.is_valid_level(level)

        assert not validator.is_valid_level("invalid")
        assert not validator.is_valid_level("")
```

### 3. Transformation Tests

```python
@pytest.mark.unit
class TestLogTransformation:
    """Unit tests for log enrichment and transformation"""

    @pytest.fixture
    def transformer(self):
        from log_worker.transformer import LogTransformer
        return LogTransformer(
            environment="test",
            version="1.0.0",
            region="us-west-2"
        )

    def test_normalize_log_levels(self, transformer):
        """Normalize various case formats to uppercase"""
        test_cases = [
            ("info", "INFO"),
            ("Info", "INFO"),
            ("INFO", "INFO"),
            ("debug", "DEBUG"),
            ("error", "ERROR"),
            ("WARN", "WARN"),
        ]

        for input_val, expected in test_cases:
            assert transformer.normalize_level(input_val) == expected

    def test_add_metadata_fields(self, transformer):
        """Add environment metadata to log"""
        log = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "info",
            "message": "Test"
        }

        enriched = transformer.enrich(log)

        assert enriched["environment"] == "test"
        assert enriched["version"] == "1.0.0"
        assert enriched["region"] == "us-west-2"
        assert enriched["processed_at"] is not None

    def test_extract_structured_fields(self, transformer):
        """Extract key=value pairs from log message"""
        log = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "info",
            "message": "Request completed duration=125ms user_id=42 endpoint=/api/v1/users status=200"
        }

        enriched = transformer.enrich(log)

        # Extracted fields should be accessible
        assert enriched.get("duration_ms") == 125
        assert enriched.get("user_id") == 42
        assert enriched.get("status") == 200

    def test_add_geolocation_from_source_ip(self, transformer):
        """Enrich log with geolocation if IP present"""
        log = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "info",
            "message": "Login attempt",
            "source_ip": "203.0.113.42"
        }

        enriched = transformer.enrich(log)

        # Should lookup geolocation
        assert "source_country" in enriched or "source_ip" in enriched
```

### 4. Metrics Worker Tests

```python
@pytest.mark.unit
class TestMetricsAggregation:
    """Unit tests for metrics aggregation logic"""

    @pytest.fixture
    def aggregator(self):
        from metrics_worker.aggregator import MetricsAggregator
        return MetricsAggregator()

    def test_aggregate_counter_values(self, aggregator):
        """Aggregate multiple counter values"""
        metrics = [
            {"name": "requests", "value": 100, "type": "counter"},
            {"name": "requests", "value": 50, "type": "counter"},
            {"name": "requests", "value": 75, "type": "counter"},
        ]

        result = aggregator.aggregate(metrics)

        assert result.sum == 225
        assert result.count == 3
        assert result.avg == 75.0

    def test_aggregate_gauge_latest_value(self, aggregator):
        """For gauge metrics, use latest value"""
        metrics = [
            {"name": "memory_usage", "value": 500, "timestamp": 1000},
            {"name": "memory_usage", "value": 600, "timestamp": 2000},
            {"name": "memory_usage", "value": 550, "timestamp": 3000},
        ]

        result = aggregator.aggregate(metrics)

        assert result.value == 550  # Latest

    def test_aggregate_histogram_percentiles(self, aggregator):
        """Calculate percentiles for histogram"""
        values = list(range(1, 101))  # 1-100
        metrics = [{"name": "latency_ms", "value": v, "type": "histogram"} for v in values]

        result = aggregator.aggregate(metrics)

        assert result.p50 == 50
        assert result.p95 == 95
        assert result.p99 == 99

    def test_ignore_old_metrics(self, aggregator):
        """Ignore metrics older than configured window"""
        now = int(time.time())
        metrics = [
            {"name": "requests", "value": 100, "timestamp": now},
            {"name": "requests", "value": 50, "timestamp": now - 3600},  # 1 hour old
        ]

        result = aggregator.aggregate(metrics, window_seconds=1800)  # 30 min window

        # Old metric should be ignored
        assert result.count == 1
        assert result.sum == 100
```

## Integration Tests: Queue to Output

### 1. Redis Stream Consumption

```python
import json
import time

@pytest.mark.integration
@pytest.mark.requires_db
class TestWorkerQueueConsumption:
    """Integration tests for worker Redis consumption"""

    def test_worker_consumes_from_redis_stream(self, redis_client, log_worker):
        """Worker should read and acknowledge messages from Redis Stream"""
        # Setup: Add log to stream
        log = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "test",
            "level": "info",
            "message": "Integration test log"
        }
        message_id = redis_client.xadd('logs-stream', {'data': json.dumps(log)})

        # Execute: Worker processes
        log_worker.process_batch(count=1)

        # Verify: Message acknowledged
        pending = redis_client.xpending('logs-stream', 'log-worker-group')
        assert pending['pending'] == 0  # All acknowledged

    def test_worker_handles_dead_letter_queue(self, redis_client, log_worker):
        """Worker should move failed messages to DLQ"""
        # Add invalid message
        redis_client.xadd('logs-stream', {'data': 'invalid json'})

        # Process (should fail and DLQ)
        log_worker.process_batch(count=1, max_retries=0)

        # Verify: Message in DLQ
        dlq_messages = redis_client.xlen('logs-stream:dlq')
        assert dlq_messages > 0

    def test_worker_respects_batch_size(self, redis_client, log_worker):
        """Worker should process only up to configured batch size"""
        # Add 100 messages
        for i in range(100):
            log = {
                "timestamp": "2024-01-06T12:00:00Z",
                "service": "test",
                "level": "info",
                "message": f"Log {i}"
            }
            redis_client.xadd('logs-stream', {'data': json.dumps(log)})

        # Process with batch size 10
        log_worker.process_batch(count=10)

        # Verify: Only 10 processed
        remaining = redis_client.xlen('logs-stream')
        assert remaining == 90
```

### 2. Output Verification

```python
@pytest.mark.integration
def test_logs_indexed_in_elasticsearch(redis_client, elasticsearch_client, log_worker):
    """Processed logs should be indexed in Elasticsearch"""
    # Add log
    log = {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "app",
        "level": "error",
        "message": "Critical error occurred"
    }
    redis_client.xadd('logs-stream', {'data': json.dumps(log)})

    # Process
    log_worker.process_batch(count=1)

    # Verify: Indexed
    time.sleep(1)  # Allow indexing
    result = elasticsearch_client.search(
        index='logs-*',
        query={"match": {"message": "Critical error"}}
    )

    assert result['hits']['total']['value'] > 0

@pytest.mark.integration
def test_metrics_stored_in_database(redis_client, db_session, metrics_worker):
    """Aggregated metrics should be persisted"""
    # Add metrics
    for i in range(5):
        metric = {
            "name": "cpu_usage",
            "value": 50 + i,
            "timestamp": int(time.time())
        }
        redis_client.xadd('metrics-stream', {'data': json.dumps(metric)})

    # Process
    metrics_worker.process_batch(count=5)

    # Verify: In database
    from shared.models import AggregatedMetric
    agg = db_session.query(AggregatedMetric).filter_by(name='cpu_usage').first()

    assert agg is not None
    assert agg.count == 5
```

### 3. Error Recovery

```python
@pytest.mark.integration
@pytest.mark.slow
def test_worker_retries_on_transient_failure(redis_client, elasticsearch_client,
                                               log_worker, mocker):
    """Worker should retry on temporary failures"""
    # Mock ES to fail once, then succeed
    call_count = {'count': 0}
    original_bulk = elasticsearch_client.bulk

    def mock_bulk(*args, **kwargs):
        call_count['count'] += 1
        if call_count['count'] == 1:
            raise TimeoutError("Connection timeout")
        return original_bulk(*args, **kwargs)

    mocker.patch.object(elasticsearch_client, 'bulk', side_effect=mock_bulk)

    # Add log
    log = {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "test",
        "level": "info",
        "message": "Retry test"
    }
    redis_client.xadd('logs-stream', {'data': json.dumps(log)})

    # Process with retries
    log_worker.process_batch(count=1, max_retries=2)

    # Should have retried
    assert call_count['count'] >= 2

@pytest.mark.integration
def test_worker_survives_partial_batch_failure(redis_client, log_worker):
    """Worker should continue processing after failures"""
    logs = [
        {"timestamp": "2024-01-06T12:00:00Z", "service": "app", "level": "info", "message": "valid"},
        {"invalid": "log"},  # Invalid
        {"timestamp": "2024-01-06T12:00:02Z", "service": "app", "level": "info", "message": "valid"},
    ]

    for log in logs:
        redis_client.xadd('logs-stream', {'data': json.dumps(log)})

    # Should not crash
    results = log_worker.process_batch(count=3, stop_on_error=False)

    assert results['success'] == 2
    assert results['failed'] == 1
```

## Performance Tests

```python
@pytest.mark.performance
@pytest.mark.slow
def test_worker_throughput(redis_client, log_worker, benchmark):
    """Measure log processing throughput"""
    # Setup: 1000 logs
    logs = [
        {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "perf-test",
            "level": "info",
            "message": f"Log {i}"
        }
        for i in range(1000)
    ]

    for log in logs:
        redis_client.xadd('logs-stream', {'data': json.dumps(log)})

    # Benchmark
    def process():
        log_worker.process_batch(count=1000)

    result = benchmark(process)

    # Should process >100 logs/sec
    assert result < 10  # Max 10 seconds for 1000 logs
```

## Test Best Practices for Workers

1. **Use Separate Redis DB for Tests**

   ```python
   redis_client = redis.Redis(db=15)  # Use DB 15 for tests
   ```

2. **Clean Up Between Tests**

   ```python
   @pytest.fixture
   def redis_client():
       client = redis.Redis(db=15)
       yield client
       client.delete('logs-stream', 'metrics-stream')  # Cleanup
   ```

3. **Test Idempotency**

   ```python
   def test_worker_is_idempotent():
       """Processing same message twice should be safe"""
       # Process once
       log_worker.process_batch()
       result1 = get_results()

       # Process same messages again (in DLQ recovery)
       log_worker.process_batch()
       result2 = get_results()

       # Should have same data
       assert result1 == result2
   ```

4. **Monitor Resource Usage**

   ```python
   @pytest.mark.performance
   def test_worker_memory_usage():
       """Worker should not leak memory"""
       import tracemalloc

       tracemalloc.start()

       for _ in range(1000):
           log_worker.process_batch(count=1)

       current, peak = tracemalloc.get_traced_memory()

       # Memory should not exceed threshold
       assert peak < 500 * 1024 * 1024  # 500 MB
   ```

---

**Last Updated**: 2026-01-07
**Scope**: Worker-specific testing patterns, queue integration, output verification
