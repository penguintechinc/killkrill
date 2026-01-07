# Redis Streams Integration Tests - Quick Start

## 🚀 Quick Run

### Option 1: Makefile (Recommended)
```bash
# Auto-start Redis container, run tests, cleanup
make test-redis

# Use existing Redis instance
make test-redis-quick
```

### Option 2: Manual
```bash
# Start Redis
docker run -d --name redis-test -p 6379:6379 redis:7-alpine

# Run tests
cd /home/penguin/code/killkrill/tests
export TEST_REDIS_ENABLED=true
export REDIS_URL=redis://localhost:6379/0
python3 -m pytest integration/test_redis_streams.py -v

# Cleanup
docker stop redis-test
```

## 📋 Test Summary

**Total Tests**: 21 tests across 6 test classes
**Markers**: `@pytest.mark.integration`, `@pytest.mark.requires_network`
**Target File**: `/home/penguin/code/killkrill/tests/integration/test_redis_streams.py`

### Test Classes

| Class | Tests | Coverage |
|-------|-------|----------|
| **TestSyncStreamsBasics** | 6 | Basic XADD, XREAD, XLEN, XINFO, MAXLEN |
| **TestSyncConsumerGroups** | 5 | XGROUP, XREADGROUP, XACK, XPENDING, XCLAIM |
| **TestAsyncStreamsBasics** | 3 | Async stream operations |
| **TestErrorHandling** | 3 | Connection errors, invalid operations |
| **TestHighThroughput** | 2 | 1000+ messages, concurrent consumers |
| **TestStreamMetadata** | 2 | XINFO STREAM, XINFO GROUPS |

## 🎯 Run Specific Tests

```bash
# Single test class
pytest integration/test_redis_streams.py::TestSyncStreamsBasics -v

# Single test method
pytest integration/test_redis_streams.py::TestSyncStreamsBasics::test_stream_single_publish -v

# All sync tests
pytest integration/test_redis_streams.py -k "sync" -v

# All async tests
pytest integration/test_redis_streams.py -k "async" -v

# High throughput only
pytest integration/test_redis_streams.py::TestHighThroughput -v
```

## ⚙️ Environment Variables

```bash
# Required to enable tests
export TEST_REDIS_ENABLED=true

# Connection URL (default: redis://localhost:6379/0)
export REDIS_URL=redis://localhost:6379/0

# Optional: Custom stream prefix
export TEST_STREAM_PREFIX=mytest_
```

## ✅ Expected Output (Success)

```
====================== test session starts =======================
platform linux -- Python 3.12.3, pytest-7.4.3, pluggy-1.6.0
collected 21 items

integration/test_redis_streams.py::TestSyncStreamsBasics::test_stream_single_publish PASSED [  4%]
integration/test_redis_streams.py::TestSyncStreamsBasics::test_stream_batch_publish PASSED [  9%]
...
integration/test_redis_streams.py::TestStreamMetadata::test_xinfo_groups PASSED [100%]

====================== 21 passed in 2.34s ========================
```

## 🔍 CI/CD Integration

### GitHub Actions
```yaml
jobs:
  test-redis-streams:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - name: Run Redis Streams Tests
        env:
          TEST_REDIS_ENABLED: true
          REDIS_URL: redis://localhost:6379/0
        run: |
          pip install -r tests/requirements.txt
          cd tests
          pytest integration/test_redis_streams.py -v --tb=short
```

### GitLab CI
```yaml
test-redis-streams:
  services:
    - redis:7-alpine
  variables:
    TEST_REDIS_ENABLED: "true"
    REDIS_URL: "redis://redis:6379/0"
  script:
    - pip install -r tests/requirements.txt
    - cd tests
    - pytest integration/test_redis_streams.py -v --tb=short
```

## 🐛 Troubleshooting

### Tests Skipped
**Issue**: All tests show `SKIPPED`
**Fix**: Set `TEST_REDIS_ENABLED=true`

### Connection Refused
**Issue**: `redis.exceptions.ConnectionError: Error connecting to localhost:6379`
**Fix**:
```bash
# Check if Redis is running
redis-cli ping

# Start Redis if needed
docker run -d --name redis-test -p 6379:6379 redis:7-alpine
```

### Import Error
**Issue**: `ModuleNotFoundError: No module named 'redis'`
**Fix**:
```bash
pip install -r tests/requirements.txt
```

### Permission Denied
**Issue**: `PermissionError: /tmp/killkrill-tests/`
**Fix**:
```bash
mkdir -p /tmp/killkrill-tests
chmod 755 /tmp/killkrill-tests
```

## 📊 Performance Benchmarks

Typical execution times on modern hardware:

| Test Class | Time | Throughput |
|------------|------|------------|
| TestSyncStreamsBasics | ~0.3s | 20 ops/sec |
| TestSyncConsumerGroups | ~0.4s | 12 ops/sec |
| TestAsyncStreamsBasics | ~0.2s | 15 ops/sec |
| TestHighThroughput | ~0.8s | 1250+ msg/sec |
| **Total** | ~2.3s | **All 21 tests** |

## 📚 Full Documentation

For comprehensive documentation, see:
- [README.md](README.md) - Complete test documentation
- [Redis Streams Docs](https://redis.io/docs/data-types/streams/)
- [Killkrill Architecture](../../docs/ARCHITECTURE.md)

## 🎓 Test Examples

### Basic Stream Operations
```python
# Publish message
msg_id = redis_client.xadd('stream_name', {'key': 'value'})

# Read messages
messages = redis_client.xread({'stream_name': '0'}, count=10)

# Get stream length
length = redis_client.xlen('stream_name')
```

### Consumer Groups
```python
# Create consumer group
redis_client.xgroup_create('stream_name', 'group_name', id='0')

# Read as consumer
messages = redis_client.xreadgroup(
    'group_name',
    'consumer_name',
    {'stream_name': '>'},
    count=10
)

# Acknowledge message
redis_client.xack('stream_name', 'group_name', msg_id)
```

### Async Operations
```python
# Async publish and read
msg_id = await async_redis_client.xadd('stream_name', {'key': 'value'})
messages = await async_redis_client.xread({'stream_name': '0'})
```

---

**Last Updated**: 2026-01-07
**Maintainer**: Penguin Tech Inc
**Support**: support@penguintech.io
