# Worker Tests - Implementation Notes

## Import Path Handling

The worker services are in directories with hyphens:

- `apps/log-worker/app.py`
- `apps/metrics-worker/app.py`

Python imports don't support hyphens in module names. Tests handle this by:

1. **Direct Path Import**: Tests patch the actual module after it's loaded
2. **PYTHONPATH Setup**: Ensure project root is in PYTHONPATH
3. **sys.path Manipulation**: Workers add parent directory to sys.path

### Running Tests

```bash
# From project root
export PYTHONPATH=/home/penguin/code/killkrill:$PYTHONPATH
cd tests
pytest workers/ -v
```

### Alternative: Use importlib for Dynamic Imports

If direct imports fail, tests use importlib:

```python
import importlib.util
import sys

# Load log-worker module
spec = importlib.util.spec_from_file_location(
    "log_worker_app",
    "/home/penguin/code/killkrill/apps/log-worker/app.py"
)
log_worker = importlib.util.module_from_spec(spec)
sys.modules['apps.log_worker.app'] = log_worker
spec.loader.exec_module(log_worker)
```

## Test Execution Modes

### 1. Unit Tests (Fast)

- All dependencies mocked
- No external services required
- Run time: <1s per test

```bash
pytest workers/ -m unit
```

### 2. Integration Tests (Mocked Services)

- Mock Redis, Elasticsearch, Prometheus
- Test component interactions
- Run time: ~2s per test

```bash
pytest workers/ -m integration
```

### 3. End-to-End Tests (Real Services)

- Requires Docker Compose services
- Full pipeline testing
- Run time: Variable (10-30s per test)

```bash
# Start services first
docker-compose -f docker-compose.test.yml up -d

# Run E2E tests
pytest workers/ -m e2e

# Cleanup
docker-compose -f docker-compose.test.yml down
```

## Mock Strategy

### Redis Streams Mocking

```python
# Mock xreadgroup to return messages
mock_redis.xreadgroup.return_value = [
    (b'logs:raw', [
        (b'1234567890-0', {b'message': b'test'})
    ])
]
```

### Elasticsearch Mocking

```python
# Mock bulk operation
with patch('elasticsearch.helpers.bulk', return_value=(10, [])):
    # Test code that uses ES
```

### Prometheus Mocking

```python
# Mock HTTP POST to pushgateway
with patch('requests.post') as mock_post:
    mock_post.return_value = Mock(status_code=200)
    # Test code
```

## Test Data Conventions

### Log Messages

- Use realistic syslog format
- Include all required ECS fields
- Test with optional fields (trace_id, span_id, etc.)

### Metrics

- Cover all metric types: counter, gauge, histogram, summary
- Include labels in JSON format
- Test timestamp handling (ISO8601)

### Message IDs

- Format: `{timestamp_ms}-{sequence}`
- Example: `1704623400000-0`

## Performance Targets

- **Log Worker**: 50K+ events/sec per worker
- **Metrics Worker**: 50K+ metrics/sec per worker
- **Batch Processing**: <100ms per batch (100 items)
- **Queue Lag**: <1000 messages under normal load

## Common Test Failures

### 1. Import Errors

**Problem**: Cannot import worker modules
**Solution**: Set PYTHONPATH or use importlib

### 2. Prometheus Metrics Already Registered

**Problem**: Metrics registered in previous test
**Solution**: Use `reset_metrics` fixture (auto-applied)

### 3. Redis Connection Refused

**Problem**: Real Redis client trying to connect
**Solution**: Ensure mock_redis fixture is used

### 4. Elasticsearch Timeout

**Problem**: Real ES client trying to connect
**Solution**: Ensure mock_elasticsearch_client fixture is used

## Debugging Tips

### Enable Verbose Logging

```bash
pytest workers/ -v --log-cli-level=DEBUG
```

### Run Single Test

```bash
pytest workers/test_log_worker.py::TestElasticsearchProcessor::test_process_logs_batch_success -v
```

### Print Captured Output

```bash
pytest workers/ -v -s  # -s disables output capture
```

### Debug with PDB

```python
def test_something():
    import pdb; pdb.set_trace()
    # Test code
```

## Test Coverage Goals

- **Line Coverage**: >90%
- **Branch Coverage**: >85%
- **Critical Paths**: 100% (error handling, shutdown)

Current coverage:

```bash
pytest workers/ --cov=apps.log_worker --cov=apps.metrics_worker --cov-report=term-missing
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
- name: Run Worker Tests
  run: |
    export PYTHONPATH=$PWD:$PYTHONPATH
    cd tests
    pytest workers/ -m "not e2e" \
      --cov=apps.log_worker \
      --cov=apps.metrics_worker \
      --junitxml=test-results.xml \
      --cov-report=xml
```

### Docker-Based Testing

```dockerfile
FROM python:3.12-slim

# Install dependencies
COPY requirements.txt tests/requirements.txt tests/workers/requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

# Copy code
COPY apps/ /app/apps/
COPY tests/ /app/tests/
COPY shared/ /app/shared/

# Run tests
WORKDIR /app/tests
ENV PYTHONPATH=/app
CMD ["pytest", "workers/", "-v"]
```

## Future Improvements

1. **Chaos Testing**: Test worker behavior under failures
   - Sudden Redis disconnection
   - Elasticsearch throttling (429 errors)
   - OOM conditions

2. **Load Testing**: Verify throughput claims
   - Sustained 50K+ msg/sec per worker
   - Memory usage under load
   - CPU utilization patterns

3. **Fault Injection**: Test error recovery
   - Corrupt message data
   - Invalid JSON in labels
   - Missing required fields

4. **Multi-Worker Tests**: Test coordination
   - Consumer group message distribution
   - Pending message claims
   - No duplicate processing

5. **Monitoring Tests**: Verify metrics accuracy
   - Counter increments match processed count
   - Histogram buckets are correct
   - Gauge values update properly
