# Redis Streams Integration Tests

Comprehensive integration tests for Redis streams operations in killkrill.

## Test Coverage

### Basic Operations

- **Stream publishing (XADD)**: Single message and batch operations
- **Stream consuming (XREAD)**: Blocking and non-blocking reads
- **Stream trimming**: MAXLEN constraint for backpressure handling
- **Stream info**: XINFO STREAM, XLEN commands

### Consumer Groups

- **Group creation**: XGROUP CREATE with error handling
- **Group reading**: XREADGROUP with multiple consumers
- **Message acknowledgment**: XACK operations
- **Pending messages**: XPENDING tracking
- **Message claiming**: XCLAIM for rebalancing

### Advanced Scenarios

- **High throughput**: Batch publishing of 1000+ messages
- **Concurrent consumers**: Multiple consumers reading simultaneously
- **Error handling**: Connection failures, duplicate groups, invalid operations
- **Async operations**: Full async/await support with aioredis

## Prerequisites

### Required Dependencies

```bash
pip install -r ../requirements.txt
```

Key packages:

- `pytest>=7.4.3`
- `pytest-asyncio>=0.23.2`
- `redis>=5.0.1`

### Redis Server

Tests require a running Redis server. Options:

**Option 1: Docker (Recommended)**

```bash
docker run -d --name redis-test -p 6379:6379 redis:7-alpine
```

**Option 2: Local Redis**

```bash
# Install Redis
sudo apt-get install redis-server  # Debian/Ubuntu
brew install redis                  # macOS

# Start Redis
redis-server
```

**Option 3: Mock Mode (Unit-style)**
Tests automatically skip when Redis is unavailable unless `TEST_REDIS_ENABLED=true`.

## Running Tests

### Enable Integration Tests

```bash
# Set environment variable to enable Redis tests
export TEST_REDIS_ENABLED=true
export REDIS_URL=redis://localhost:6379/0
```

### Run All Redis Stream Tests

```bash
cd /home/penguin/code/killkrill/tests
pytest integration/test_redis_streams.py -v
```

### Run Specific Test Classes

```bash
# Sync client tests only
pytest integration/test_redis_streams.py::TestSyncStreamsBasics -v

# Async client tests only
pytest integration/test_redis_streams.py::TestAsyncStreamsBasics -v

# Consumer group tests
pytest integration/test_redis_streams.py::TestSyncConsumerGroups -v

# High throughput tests
pytest integration/test_redis_streams.py::TestHighThroughput -v
```

### Run by Marker

```bash
# All integration tests
pytest -m integration

# Integration tests requiring network
pytest -m "integration and requires_network"

# Skip integration tests
pytest -m "not integration"
```

### Run with Coverage

```bash
pytest integration/test_redis_streams.py \
  --cov=apps/api/services \
  --cov=apps/log-receiver \
  --cov=apps/metrics-receiver \
  --cov-report=html:/tmp/killkrill-tests/coverage
```

## Environment Variables

| Variable             | Default                    | Description                    |
| -------------------- | -------------------------- | ------------------------------ |
| `TEST_REDIS_ENABLED` | `false`                    | Enable Redis integration tests |
| `REDIS_URL`          | `redis://localhost:6379/0` | Redis connection URL           |
| `TEST_STREAM_PREFIX` | `test_stream_`             | Prefix for test stream names   |

## Test Output

Tests use `/tmp/killkrill-tests/` for temporary data:

- Coverage reports: `/tmp/killkrill-tests/coverage/`
- Test results: `/tmp/killkrill-tests/test-results.xml`
- Logs: `/tmp/killkrill-tests/test-output.log`

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Start Redis
  run: |
    docker run -d --name redis-test -p 6379:6379 redis:7-alpine

- name: Run Integration Tests
  env:
    TEST_REDIS_ENABLED: true
    REDIS_URL: redis://localhost:6379/0
  run: |
    pytest tests/integration/test_redis_streams.py -v --tb=short

- name: Stop Redis
  if: always()
  run: docker stop redis-test
```

### Makefile Target

```makefile
test-integration-redis:
	@echo "Starting Redis container..."
	docker run -d --rm --name redis-test -p 6379:6379 redis:7-alpine
	@echo "Running Redis streams integration tests..."
	TEST_REDIS_ENABLED=true REDIS_URL=redis://localhost:6379/0 \
		pytest tests/integration/test_redis_streams.py -v
	@echo "Stopping Redis container..."
	docker stop redis-test
```

## Troubleshooting

### Tests Skipped

```
tests/integration/test_redis_streams.py::TestSyncStreamsBasics SKIPPED
```

**Solution**: Set `TEST_REDIS_ENABLED=true` and ensure Redis is running.

### Connection Timeout

```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solution**:

1. Verify Redis is running: `redis-cli ping`
2. Check REDIS_URL: `echo $REDIS_URL`
3. Test connection: `redis-cli -u $REDIS_URL ping`

### Import Errors

```
ModuleNotFoundError: No module named 'redis'
```

**Solution**: Install test dependencies: `pip install -r tests/requirements.txt`

### Permission Errors

```
PermissionError: [Errno 13] Permission denied: '/tmp/killkrill-tests/'
```

**Solution**: Create directory with proper permissions:

```bash
mkdir -p /tmp/killkrill-tests
chmod 755 /tmp/killkrill-tests
```

## Test Architecture

### Fixtures

**Connection Fixtures**:

- `redis_client`: Synchronous Redis client with auto-cleanup
- `async_redis_client`: Async Redis client for asyncio tests
- `redis_available`: Session-scoped availability check

**Resource Fixtures**:

- `test_stream_name`: Unique stream name per test
- `test_consumer_group`: Unique consumer group name
- `test_consumer_name`: Unique consumer name
- `cleanup_stream`: Auto-cleanup after test completion

### Test Classes

1. **TestSyncStreamsBasics**: Core stream operations (sync)
2. **TestSyncConsumerGroups**: Consumer group management (sync)
3. **TestAsyncStreamsBasics**: Async stream operations
4. **TestErrorHandling**: Error scenarios and edge cases
5. **TestHighThroughput**: Performance and scalability
6. **TestStreamMetadata**: XINFO commands and metadata

## Performance Expectations

Typical performance on modern hardware:

- **Single publish**: < 1ms per message
- **Batch publish (100 messages)**: < 10ms
- **Consumer group read**: < 5ms per operation
- **High volume test (1000 messages)**: < 500ms
- **Concurrent consumers (5x)**: < 1000ms total

## Integration with Killkrill

These tests validate Redis streams functionality used by:

- **Log Receiver** (`apps/log-receiver`): High-throughput log ingestion
- **Metrics Receiver** (`apps/metrics-receiver`): Metrics data ingestion
- **Log Worker** (`apps/log-worker`): Async log processing from streams
- **Metrics Worker** (`apps/metrics-worker`): Metrics aggregation pipeline
- **API Service** (`apps/api`): Redis caching and coordination

## References

- [Redis Streams Documentation](https://redis.io/docs/data-types/streams/)
- [redis-py Streams Guide](https://redis-py.readthedocs.io/en/stable/examples/redis-stream-example.html)
- [Killkrill Architecture](../../docs/ARCHITECTURE.md)
- [Testing Standards](../../docs/STANDARDS.md#testing)

## Maintenance

**Last Updated**: 2026-01-07
**Test File**: `tests/integration/test_redis_streams.py`
**Maintainer**: Penguin Tech Inc
**Issues**: https://github.com/penguintechinc/killkrill/issues
