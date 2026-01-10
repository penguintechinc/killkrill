# End-to-End Tests

Comprehensive E2E tests for Killkrill data pipelines (logs and metrics).

## Test Files

- `test_log_pipeline.py` - Log pipeline E2E tests (8 tests)
- `test_metrics_pipeline.py` - Metrics pipeline E2E tests (13 tests)

## Prerequisites

### Required Services

All services must be running before executing E2E tests:

```bash
# Start all services via Docker Compose
docker-compose -f docker-compose.yml up -d

# Verify services are running
docker-compose ps
```

**Required services:**

- **log-receiver** (port 8081)
- **metrics-receiver** (port 8082)
- **log-worker** (background)
- **metrics-worker** (background)
- **API service** (port 8080)
- **Redis** (port 6379)
- **PostgreSQL** (port 5432)

### Environment Variables

Configure service URLs via environment variables:

```bash
export LOG_RECEIVER_URL=http://localhost:8081
export METRICS_RECEIVER_URL=http://localhost:8082
export API_BASE_URL=http://localhost:8080
export REDIS_URL=redis://localhost:6379
```

**Defaults:**

- `LOG_RECEIVER_URL`: http://localhost:8081
- `METRICS_RECEIVER_URL`: http://localhost:8082
- `API_BASE_URL`: http://localhost:8080
- `REDIS_URL`: redis://localhost:6379

## Running Tests

### Run All E2E Tests

```bash
# From tests/ directory
pytest e2e/ -v -m e2e

# From project root
pytest tests/e2e/ -v -m e2e
```

### Run Specific Pipeline Tests

```bash
# Log pipeline tests only
pytest tests/e2e/test_log_pipeline.py -v

# Metrics pipeline tests only
pytest tests/e2e/test_metrics_pipeline.py -v
```

### Run Specific Test Cases

```bash
# Single test
pytest tests/e2e/test_log_pipeline.py::test_single_log_submission -v

# Multiple tests by pattern
pytest tests/e2e/ -k "data_integrity" -v
```

### Skip Slow Tests

```bash
# Skip slow tests (marked with @pytest.mark.slow)
pytest tests/e2e/ -v -m "e2e and not slow"
```

### Verbose Output with Logs

```bash
# Show detailed output including print statements
pytest tests/e2e/ -v -s

# Show captured logs
pytest tests/e2e/ -v --log-cli-level=INFO
```

## Test Categories

### Log Pipeline Tests

1. **test_single_log_submission** - Submit single log via HTTP POST
2. **test_batch_log_submission** - Submit multiple logs sequentially
3. **test_different_log_levels** - Test DEBUG, INFO, WARN, ERROR levels
4. **test_log_worker_processing** - Verify worker consumes from Redis
5. **test_complete_log_pipeline** - Full pipeline from receiver to API
6. **test_log_data_integrity** - Verify timestamps and labels preserved
7. **test_log_receiver_health_check** - Health endpoint validation
8. **test_log_submission_validation** - Input validation tests

### Metrics Pipeline Tests

1. **test_single_metric_submission** - Submit single metric via HTTP POST
2. **test_counter_metric_type** - Test counter metric type
3. **test_gauge_metric_type** - Test gauge metric type
4. **test_histogram_metric_type** - Test histogram metric type
5. **test_different_metric_types** - Test all metric types
6. **test_metrics_labels_handling** - Verify labels/tags preservation
7. **test_batch_metrics_submission** - Submit multiple metrics
8. **test_metrics_worker_processing** - Verify worker consumes from Redis
9. **test_metrics_aggregation** - Test metric aggregation
10. **test_complete_metrics_pipeline** - Full pipeline from receiver to API
11. **test_metric_data_integrity** - Verify values, types, labels preserved
12. **test_metrics_receiver_health_check** - Health endpoint validation
13. **test_metric_submission_validation** - Input validation tests

## Test Markers

- `@pytest.mark.e2e` - E2E tests (requires running services)
- `@pytest.mark.requires_network` - Requires network access
- `@pytest.mark.slow` - Slow-running tests (>10 seconds)

## Test Approach

### Data Flow Verification

Each test verifies data integrity through the complete pipeline:

1. **Submit** - POST data to receiver endpoint
2. **Redis Stream** - Poll Redis stream for data
3. **Worker Processing** - Allow time for worker to process
4. **API Query** - Query processed data via API
5. **Assertions** - Verify data integrity at each step

### Unique Test Identifiers

All test data includes unique identifiers (UUIDs) to track data through the pipeline and avoid false positives from previous test runs.

### Polling with Timeout

Tests use configurable polling with timeout to wait for async processing:

```python
PROCESSING_TIMEOUT = 30  # seconds
POLL_INTERVAL = 0.5      # seconds
```

### Graceful Skipping

Tests automatically skip if required services are unavailable, rather than failing:

```python
@pytest.fixture(scope='module')
def log_receiver_available():
    try:
        response = requests.get(f"{LOG_RECEIVER_URL}/healthz", timeout=5)
        if response.status_code == 200:
            return True
        pytest.skip(f"Log receiver unhealthy: {response.status_code}")
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Log receiver not available: {e}")
```

## Key Assertions

### Log Pipeline

- Log submission returns 200/202 status
- Log appears in Redis stream within timeout
- Log level preserved (DEBUG, INFO, WARN, ERROR)
- Timestamp preserved in ISO format
- Labels preserved as JSON
- Worker processes and acknowledges messages
- Health check includes Redis and database status

### Metrics Pipeline

- Metric submission returns 200/202 status
- Metric appears in Redis stream within timeout
- Metric type preserved (counter, gauge, histogram)
- Metric value preserved with precision
- Labels/tags preserved as JSON
- Worker processes and aggregates metrics
- Health check includes Redis and database status

## Troubleshooting

### Tests Skip with "Service not available"

**Cause:** Required services not running

**Solution:**

```bash
# Check service health
curl http://localhost:8081/healthz  # log-receiver
curl http://localhost:8082/healthz  # metrics-receiver
curl http://localhost:8080/healthz  # API

# Start services if needed
docker-compose up -d
```

### Tests Timeout Waiting for Redis

**Cause:** Worker services not processing messages

**Solution:**

```bash
# Check worker logs
docker-compose logs log-worker
docker-compose logs metrics-worker

# Verify Redis stream
redis-cli XINFO STREAM logs:raw
redis-cli XINFO STREAM metrics:raw
```

### Tests Fail with Connection Refused

**Cause:** Service ports not exposed or firewall blocking

**Solution:**

```bash
# Verify port bindings
docker-compose ps

# Check port accessibility
telnet localhost 8081
telnet localhost 8082
telnet localhost 8080
telnet localhost 6379
```

### Redis Authentication Errors

**Cause:** Redis requires authentication but REDIS_URL doesn't include credentials

**Solution:**

```bash
# Update REDIS_URL with authentication
export REDIS_URL=redis://:password@localhost:6379
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: killkrill
          POSTGRES_USER: killkrill
          POSTGRES_PASSWORD: killkrill123
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Build and start services
        run: |
          docker-compose up -d
          sleep 10  # Wait for services to initialize

      - name: Run E2E tests
        run: |
          pytest tests/e2e/ -v -m e2e --junitxml=test-results.xml

      - name: Cleanup
        if: always()
        run: docker-compose down -v
```

## Performance Notes

- **Average test duration**: 5-15 seconds per test
- **Slow tests** (marked `@pytest.mark.slow`): 15-30 seconds
- **Full suite runtime**: ~3-5 minutes with all services running
- **Parallel execution**: Not recommended due to shared Redis streams

## Future Enhancements

- [ ] API query endpoint implementation for full pipeline verification
- [ ] Elasticsearch integration tests for log-worker
- [ ] Prometheus Gateway tests for metrics-worker
- [ ] Consumer group lag monitoring tests
- [ ] Multi-worker concurrency tests
- [ ] Message acknowledgment retry tests
- [ ] Stream cleanup between tests

## Additional Resources

- [Killkrill Architecture](../../docs/architecture.md)
- [Pipeline Documentation](../../docs/pipelines.md)
- [Development Guide](../../docs/DEVELOPMENT.md)
- [API Documentation](../../docs/api.md)
