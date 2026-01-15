# Worker Service Tests

Comprehensive test suite for KillKrill worker services (log-worker and metrics-worker).

## Test Structure

```
workers/
├── conftest.py              # Shared fixtures and test utilities
├── test_log_worker.py       # Log worker tests (35 tests)
├── test_metrics_worker.py   # Metrics worker tests (30 tests)
├── requirements.txt         # Test-specific dependencies
└── README.md               # This file
```

## Test Categories

### Integration Tests (`@pytest.mark.integration`)

- Mock external dependencies (Redis, Elasticsearch, Prometheus)
- Test component interactions
- Verify business logic and data transformations
- Fast execution (~1-2 seconds per test)

### End-to-End Tests (`@pytest.mark.e2e`)

- Require real service instances
- Test complete data pipelines
- Currently skipped by default (require infrastructure)

## Running Tests

### All Worker Tests

```bash
# From project root
pytest tests/workers/

# With verbose output
pytest tests/workers/ -v

# With coverage
pytest tests/workers/ --cov=apps.log_worker --cov=apps.metrics_worker
```

### Specific Test Files

```bash
# Log worker tests only
pytest tests/workers/test_log_worker.py

# Metrics worker tests only
pytest tests/workers/test_metrics_worker.py
```

### Specific Test Classes

```bash
# Elasticsearch processor tests
pytest tests/workers/test_log_worker.py::TestElasticsearchProcessor

# Prometheus destination tests
pytest tests/workers/test_metrics_worker.py::TestPrometheusDestination
```

### By Markers

```bash
# Integration tests only (mocked dependencies)
pytest tests/workers/ -m integration

# Skip E2E tests (default behavior)
pytest tests/workers/ -m "not e2e"
```

## Test Coverage

### Log Worker Tests (test_log_worker.py)

- **ElasticsearchProcessor**: 6 tests
  - Batch processing (success, partial failure, empty)
  - ECS document conversion
  - Optional fields handling
  - Invalid input handling

- **PrometheusProcessor**: 4 tests
  - Metrics batch processing
  - Metrics grouping by source/type
  - Label parsing
  - Empty batch handling

- **RedisStreamsConsumer**: 7 tests
  - Consumer group initialization
  - Message consumption and processing
  - Pending message recovery
  - Queue metrics updates
  - Message acknowledgment

- **WorkerLifecycle**: 3 tests
  - Signal handler setup
  - Worker thread management
  - Graceful shutdown

- **ErrorHandling**: 3 tests
  - Elasticsearch connection failures
  - Redis connection errors
  - Malformed message handling

- **PrometheusMetrics**: 2 tests
  - Metrics exposure
  - Counter increments

### Metrics Worker Tests (test_metrics_worker.py)

- **MetricEntry**: 3 tests
  - Valid entry creation
  - Default values
  - Pydantic validation

- **PrometheusDestination**: 6 tests
  - Initialization and buffer management
  - Flush on size/time thresholds
  - Prometheus exposition format
  - Push failure handling
  - Thread-safe access

- **MetricsWorker**: 6 tests
  - Worker initialization
  - Consumer group creation
  - Message consumption
  - Batch processing
  - Start/stop lifecycle

- **MetricAggregation**: 2 tests
  - Time window aggregation
  - Multi-metric type aggregation

- **MultipleDestinations**: 3 tests
  - HDFS destination
  - Spark destination
  - Bigtable destination
  - Multi-destination routing

- **MetricsProcessor**: 3 tests
  - Processor initialization
  - Worker thread management
  - Graceful shutdown

- **ErrorHandling**: 4 tests
  - Redis connection errors
  - Malformed metric data
  - Destination failures
  - Acknowledgment failures

- **Backpressure**: 2 tests
  - Large batch processing
  - Slow destination handling

- **PrometheusMetrics**: 2 tests
  - Metrics exposure
  - Counter increments

## Key Test Patterns

### 1. Consumer Group Membership

Tests verify proper Redis Streams consumer group behavior:

- Group creation and existence checking
- Message claiming from failed consumers
- Pending message recovery

### 2. Message Acknowledgment

Tests ensure messages are acknowledged only after successful processing:

- Successful processing → ACK
- Failed processing → No ACK (retry later)
- Idempotent processing

### 3. Batch Processing

Tests verify efficient batch operations:

- Configurable batch sizes
- Bulk operations to destinations
- Partial success handling

### 4. Error Handling

Tests ensure resilient operation:

- Connection failures (retry logic)
- Malformed data (skip and log)
- Destination errors (graceful degradation)

### 5. Graceful Shutdown

Tests verify clean shutdown:

- Signal handler registration (SIGTERM, SIGINT)
- Queue draining before exit
- Thread pool shutdown with timeout

## Fixtures Reference

### Mock Services

- `mock_redis_client`: Mock Redis client with stream operations
- `mock_elasticsearch_client`: Mock Elasticsearch with bulk operations
- `mock_license_client`: Mock license validation
- `mock_prometheus_gateway`: Mock Prometheus pushgateway

### Test Data

- `sample_log_message`: Single log message (syslog format)
- `sample_log_batch`: Batch of 10 log messages
- `sample_metric_message`: Single metric (Prometheus format)
- `sample_metric_batch`: Batch of 20 metrics (mixed types)

### Data Generators

- `redis_stream_messages(count, stream)`: Generate stream messages
- `pending_messages(count, idle_time)`: Generate pending message info
- `elasticsearch_bulk_response(success, failed)`: Generate bulk response

### Configuration

- `mock_config`: Complete configuration mock
- `reset_metrics`: Auto-cleanup of Prometheus metrics between tests

## Common Issues

### Import Errors

If you see import errors for `apps.log_worker` or `apps.metrics_worker`:

```bash
# Set PYTHONPATH to include project root
export PYTHONPATH=/home/penguin/code/killkrill:$PYTHONPATH
pytest tests/workers/
```

### Mock Not Working

Ensure you're patching the correct module path:

```python
# Correct: Patch where it's used
@patch('apps.log_worker.app.redis_client')

# Incorrect: Patch where it's defined
@patch('redis.Redis')
```

### Prometheus Metrics Conflicts

If metrics are already registered:

```python
# Use the reset_metrics fixture (auto-applied)
# Or manually reset in test
from prometheus_client import REGISTRY
collectors = list(REGISTRY._collector_to_names.keys())
for collector in collectors:
    REGISTRY.unregister(collector)
```

## Adding New Tests

### 1. Add to Existing Test Class

```python
@pytest.mark.integration
class TestElasticsearchProcessor:
    def test_new_feature(self, mock_config, mock_es):
        """Test description"""
        # Test implementation
```

### 2. Add New Test Class

```python
@pytest.mark.integration
class TestNewFeature:
    """Tests for new feature"""

    def test_feature_behavior(self, mock_redis):
        """Test description"""
        # Test implementation
```

### 3. Use Existing Fixtures

```python
def test_with_data(self, sample_log_batch, mock_redis):
    """Tests can use any fixture from conftest.py"""
    # Test implementation
```

## Performance Expectations

- **Integration tests**: <2s per test
- **Full test suite**: <30s total
- **E2E tests** (when enabled): Variable (depends on infrastructure)

## CI/CD Integration

Tests run automatically in GitHub Actions:

- On every pull request
- On push to main branch
- Scheduled nightly runs

CI command:

```bash
pytest tests/workers/ -m "not e2e" --cov=apps.log_worker --cov=apps.metrics_worker
```

## Future Enhancements

1. **Real Service Tests**: Enable E2E tests with Docker Compose
2. **Performance Tests**: Add benchmarks for throughput
3. **Chaos Tests**: Test behavior under resource constraints
4. **Load Tests**: Verify scalability with high message volumes
5. **Multi-Worker Tests**: Test coordination between multiple workers

## Related Documentation

- Worker implementation: `apps/log-worker/` and `apps/metrics-worker/`
- Architecture docs: `docs/architecture/workers.md`
- Redis Streams guide: `docs/redis-streams.md`
- Monitoring guide: `docs/monitoring.md`
