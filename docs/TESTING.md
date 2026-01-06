# KillKrill Testing Guide

Comprehensive testing documentation for KillKrill's log and metrics ingestion workers, including unit tests, integration tests, smoke tests, mock data, and multi-protocol validation.

## Overview

KillKrill's testing strategy ensures reliable log and metrics processing across multiple workers and receiver services. Testing is organized into multiple levels to ensure comprehensive coverage, fast feedback, and production-ready code:

| Test Level | Purpose | Speed | Coverage |
|-----------|---------|-------|----------|
| **Smoke Tests** | Fast verification of basic functionality | <2 min | Build, run, API health, receiver health |
| **Unit Tests** | Isolated worker function/method testing | <1 min | Log parsing, metrics parsing, validation logic |
| **Integration Tests** | Worker-to-queue and queue-to-backend verification | 2-5 min | Redis Streams flow, Elasticsearch output, Prometheus output |
| **E2E Tests** | Complete log/metrics pipelines end-to-end | 5-10 min | HTTP/Syslog ingestion → Redis → Worker → ELK/Prometheus |
| **Performance Tests** | Throughput and latency validation | 5-15 min | Log ingestion rate, metrics throughput, queue depth |

## Mock Data Scripts

### Purpose

Mock data scripts populate the Redis Streams queue and PostgreSQL database with realistic log and metrics entries for testing workers without requiring live application sources.

### Location & Structure

```
scripts/mock-data/
├── seed-all.sh              # Orchestrator: runs all seeders in order
├── seed-logs.sh             # 3-4 logs with different services/levels
├── seed-metrics.sh          # 3-4 metrics with different types
├── seed-events.sh           # 3-4 events with different patterns
└── README.md                # Instructions for running mock data
```

### Naming Convention

- **Shell scripts**: `seed-{entity-name}.sh`
- **Organization**: One seeder per logical data type (logs, metrics, events)

### Scope: 3-4 Items Per Category

Each seeder should create exactly 3-4 representative items to test worker variations:

**Example (Logs)**:
```bash
# seed-logs.sh
LOGS=(
  '{"timestamp":"2024-01-06T12:00:00Z","service":"webui","level":"info","message":"User logged in"}'
  '{"timestamp":"2024-01-06T12:00:01Z","service":"flask-backend","level":"error","message":"Database connection failed"}'
  '{"timestamp":"2024-01-06T12:00:02Z","service":"metrics-receiver","level":"warn","message":"Queue depth exceeding threshold"}'
  '{"timestamp":"2024-01-06T12:00:03Z","service":"log-worker","level":"debug","message":"Processing batch of 100 logs"}'
)
```

**Example (Metrics)**:
```bash
# seed-metrics.sh
METRICS=(
  '{"name":"http_requests_total","type":"counter","value":1000,"service":"api","timestamp":'$(date +%s)'}'
  '{"name":"log_processing_duration_seconds","type":"histogram","value":0.25,"service":"log-worker","timestamp":'$(date +%s)'}'
  '{"name":"redis_queue_depth","type":"gauge","value":5000,"service":"log-receiver","timestamp":'$(date +%s)'}'
  '{"name":"elasticsearch_index_size_bytes","type":"gauge","value":1073741824,"service":"logs-es","timestamp":'$(date +%s)'}'
)
```

### Execution

**Seed all test data**:
```bash
make seed-mock-data          # Via Makefile
bash scripts/mock-data/seed-all.sh  # Direct execution
```

**Seed specific category**:
```bash
bash scripts/mock-data/seed-logs.sh
bash scripts/mock-data/seed-metrics.sh
```

### Implementation Pattern

**Shell Script (Sending via API)**:
```bash
#!/bin/bash
# scripts/mock-data/seed-logs.sh

set -e

API_URL="${API_URL:-http://localhost:8081}"
TOKEN="${AUTH_TOKEN:-PENG-DEMO-DEMO-DEMO-DEMO-DEMO}"

LOGS=(
  '{"timestamp":"2024-01-06T12:00:00Z","service":"webui","level":"info","message":"User login successful"}'
  '{"timestamp":"2024-01-06T12:00:01Z","service":"flask-backend","level":"error","message":"Database connection timeout after 30s"}'
  '{"timestamp":"2024-01-06T12:00:02Z","service":"log-worker","level":"warn","message":"Worker processing slower than expected"}'
  '{"timestamp":"2024-01-06T12:00:03Z","service":"metrics-receiver","level":"info","message":"Received 500 metrics in 100ms"}'
)

for log in "${LOGS[@]}"; do
  curl -X POST "$API_URL/api/v1/logs" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$log" 2>/dev/null
done

echo "✓ Seeded ${#LOGS[@]} test logs"
```

**Syslog Seeder**:
```bash
#!/bin/bash
# scripts/mock-data/seed-syslog.sh

set -e

SYSLOG_HOST="${SYSLOG_HOST:-localhost}"
SYSLOG_PORT="${SYSLOG_PORT:-514}"

MESSAGES=(
  "webui: User authentication successful"
  "flask-backend: Database query executed in 125ms"
  "log-worker: Batch of 500 logs processed"
  "metrics-receiver: Prometheus scrape completed"
)

for msg in "${MESSAGES[@]}"; do
  echo "<14>$(date '+%b %d %H:%M:%S') $HOSTNAME $msg" | \
    nc -u -w0 "$SYSLOG_HOST" "$SYSLOG_PORT"
done

echo "✓ Seeded ${#MESSAGES[@]} test syslog messages"
```

### Makefile Integration

Add to `Makefile`:

```makefile
.PHONY: seed-mock-data
seed-mock-data:
	@echo "Seeding mock data for testing..."
	@bash scripts/mock-data/seed-all.sh
	@echo "✓ Mock data seeding complete"

.PHONY: clean-data
clean-data:
	@echo "Clearing mock data..."
	@redis-cli -n 0 FLUSHALL
	@echo "✓ Mock data cleared from Redis"
```

### When to Create Mock Data Scripts

**Create mock data scripts for each worker/receiver test cycle**:
- After implementing log-worker → create `seed-logs.sh`
- After implementing metrics-worker → create `seed-metrics.sh`
- After modifying receiver validation → update corresponding seeder

This ensures developers can immediately test worker logic without waiting for live data.

---

## Smoke Tests

### Purpose

Smoke tests provide fast verification that basic functionality works after code changes, preventing regressions in core components (receivers, workers, output backends).

### Requirements (Mandatory)

All KillKrill projects **MUST** implement smoke tests before committing:

- ✅ **Build Tests**: All containers build successfully without errors
- ✅ **Run Tests**: All containers start and remain healthy (log-receiver, metrics-receiver, workers)
- ✅ **Receiver Health**: Log and metrics receiver endpoints respond with health status
- ✅ **Queue Tests**: Redis Streams connectivity and acknowledgment handling
- ✅ **Backend Tests**: Elasticsearch and Prometheus connectivity

### Location & Structure

```
tests/smoke/
├── build/                   # Container build verification
│   ├── test-receivers-build.sh
│   ├── test-workers-build.sh
│   └── test-manager-build.sh
├── run/                     # Container runtime and health
│   ├── test-receivers-run.sh
│   ├── test-workers-run.sh
│   └── test-manager-run.sh
├── api/                     # Receiver API health endpoint validation
│   ├── test-log-receiver-health.sh
│   ├── test-metrics-receiver-health.sh
│   └── README.md
├── queue/                   # Redis Streams connectivity
│   ├── test-redis-streams.sh
│   └── README.md
├── backends/                # Elasticsearch and Prometheus connectivity
│   ├── test-elasticsearch.sh
│   ├── test-prometheus.sh
│   └── README.md
├── run-all.sh               # Execute all smoke tests
└── README.md                # Documentation
```

### Execution

**Run all smoke tests**:
```bash
make smoke-test              # Via Makefile
./tests/smoke/run-all.sh     # Direct execution
```

**Run specific test category**:
```bash
./tests/smoke/api/test-log-receiver-health.sh
./tests/smoke/queue/test-redis-streams.sh
./tests/smoke/backends/test-elasticsearch.sh
```

### Speed Requirement

Complete smoke test suite **MUST run in under 2 minutes** to provide fast feedback during development.

### Implementation Examples

**Build Test (Shell)**:
```bash
#!/bin/bash
# tests/smoke/build/test-receivers-build.sh

set -e

echo "Testing log-receiver build..."
cd services/log-receiver
if docker build -t log-receiver:test . 2>&1 | grep -q "Successfully tagged"; then
    echo "✓ Log receiver builds successfully"
else
    echo "✗ Log receiver build failed"
    exit 1
fi
```

**Receiver Health Check Test**:
```bash
#!/bin/bash
# tests/smoke/api/test-log-receiver-health.sh

set -e

echo "Checking log-receiver health..."
HEALTH_URL="http://localhost:8081/healthz"

RESPONSE=$(curl -s -w "\n%{http_code}" "$HEALTH_URL" 2>/dev/null)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Log receiver is healthy (HTTP $HTTP_CODE)"
    exit 0
else
    echo "✗ Log receiver is unhealthy (HTTP $HTTP_CODE)"
    exit 1
fi
```

**Redis Streams Connectivity Test**:
```bash
#!/bin/bash
# tests/smoke/queue/test-redis-streams.sh

set -e

echo "Testing Redis Streams connectivity..."

# Test basic connectivity
if redis-cli -h localhost ping | grep -q PONG; then
    echo "✓ Redis connectivity OK"
else
    echo "✗ Redis connectivity failed"
    exit 1
fi

# Test stream existence or creation
if redis-cli -h localhost XLEN logs-stream > /dev/null 2>&1; then
    echo "✓ Redis Streams available"
    exit 0
else
    echo "✗ Redis Streams unavailable"
    exit 1
fi
```

**Elasticsearch Connectivity Test**:
```bash
#!/bin/bash
# tests/smoke/backends/test-elasticsearch.sh

set -e

echo "Checking Elasticsearch health..."
ES_URL="http://localhost:9200/_cluster/health"

RESPONSE=$(curl -s -w "\n%{http_code}" "$ES_URL" 2>/dev/null)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ] && echo "$BODY" | grep -q "status"; then
    STATUS=$(echo "$BODY" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "✓ Elasticsearch is healthy (status: $STATUS)"
    exit 0
else
    echo "✗ Elasticsearch is unhealthy (HTTP $HTTP_CODE)"
    exit 1
fi
```

### Pre-Commit Integration

Smoke tests run as part of the pre-commit checklist (step 5) and **must pass before proceeding** to full test suite:

```bash
./scripts/pre-commit/pre-commit.sh
# Step 1: Linters
# Step 2: Security scans
# Step 3: No secrets
# Step 4: Build & Run
# Step 5: Smoke tests ← Must pass
# Step 6: Full tests
```

---

## Unit Tests

### Purpose

Unit tests verify individual worker functions and parsing logic in isolation with mocked dependencies.

### Location

```
tests/unit/
├── log-worker/
│   ├── test_parsing.py
│   ├── test_validation.py
│   └── test_transformation.py
├── metrics-worker/
│   ├── test_parsing.py
│   ├── test_aggregation.py
│   └── test_output.py
├── log-receiver/
│   ├── test_http_receiver.py
│   ├── test_syslog_receiver.py
│   └── test_auth.py
├── metrics-receiver/
│   ├── test_prometheus_scrape.py
│   ├── test_http_receiver.py
│   └── test_auth.py
└── shared/
    ├── test_validators.py
    └── test_serializers.py
```

### Execution

```bash
make test-unit              # All unit tests
pytest tests/unit/          # Python tests
pytest tests/unit/log-worker/  # Specific worker tests
```

### Requirements

- All dependencies must be mocked (Redis, Elasticsearch, Prometheus)
- Network calls must be stubbed
- Database access must be isolated
- Tests must run in parallel when possible
- Mock realistic log and metrics payloads

### Example: Log Parsing Unit Test

```python
# tests/unit/log-worker/test_parsing.py
import pytest
from log_worker.parser import LogParser, ParseError

def test_parse_valid_json_log():
    parser = LogParser()
    log_data = {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "webui",
        "level": "info",
        "message": "User login successful"
    }

    result = parser.parse(log_data)

    assert result.timestamp == "2024-01-06T12:00:00Z"
    assert result.service == "webui"
    assert result.level == "info"

def test_parse_missing_required_field():
    parser = LogParser()
    log_data = {
        "service": "webui",
        "level": "info"
        # Missing 'timestamp' and 'message'
    }

    with pytest.raises(ParseError) as exc:
        parser.parse(log_data)

    assert "timestamp" in str(exc.value)

def test_parse_invalid_timestamp():
    parser = LogParser()
    log_data = {
        "timestamp": "invalid-date",
        "service": "webui",
        "level": "info",
        "message": "Test"
    }

    with pytest.raises(ParseError):
        parser.parse(log_data)
```

---

## Integration Tests

### Purpose

Integration tests verify that workers correctly consume from Redis Streams, parse data, and output to Elasticsearch/Prometheus without mocking queue and backend connections.

### Location

```
tests/integration/
├── log-worker/
│   ├── test_redis_to_elasticsearch.py
│   ├── test_log_transformation.py
│   └── test_error_handling.py
├── metrics-worker/
│   ├── test_redis_to_prometheus.py
│   ├── test_metrics_aggregation.py
│   └── test_scrape_format.py
├── receivers/
│   ├── test_log_ingestion_flow.py
│   ├── test_metrics_ingestion_flow.py
│   └── test_syslog_flow.py
└── end-to-end/
    ├── test_http_to_elasticsearch.py
    └── test_prometheus_scrape_to_storage.py
```

### Execution

```bash
make test-integration       # All integration tests
pytest tests/integration/   # Python integration tests
pytest tests/integration/log-worker/  # Log worker tests
```

### Requirements

- Use real Redis Streams (test instance)
- Use real Elasticsearch (test instance)
- Use real Prometheus (test instance)
- Test complete worker workflows
- Verify message acknowledgment handling
- Test error scenarios and recovery

### Example: Log Worker to Elasticsearch Integration Test

```python
# tests/integration/log-worker/test_redis_to_elasticsearch.py
import pytest
import redis
import json
from elasticsearch import Elasticsearch
from log_worker.worker import LogWorker
from datetime import datetime

@pytest.fixture
def redis_client():
    r = redis.Redis(host='localhost', port=6379, db=1)
    r.delete('logs-stream')
    yield r
    r.delete('logs-stream')

@pytest.fixture
def elasticsearch_client():
    es = Elasticsearch(['http://localhost:9200'])
    es.indices.delete(index='logs-test-*', ignore_missing=True)
    yield es
    es.indices.delete(index='logs-test-*', ignore_missing=True)

def test_log_worker_processes_redis_stream(redis_client, elasticsearch_client):
    # Add test log to Redis Stream
    log_entry = {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "webui",
        "level": "info",
        "message": "User login successful"
    }
    redis_client.xadd('logs-stream', {'data': json.dumps(log_entry)})

    # Run worker to consume and output
    worker = LogWorker(redis_client, elasticsearch_client)
    worker.process_batch(count=1)

    # Verify log in Elasticsearch
    es_logs = elasticsearch_client.search(index='logs-*', query={'match_all': {}})
    assert len(es_logs['hits']['hits']) == 1

    log_doc = es_logs['hits']['hits'][0]['_source']
    assert log_doc['service'] == 'webui'
    assert log_doc['level'] == 'info'
```

---

## End-to-End Tests

### Purpose

E2E tests verify complete pipelines from ingestion (HTTP/Syslog) through workers to final backends (Elasticsearch/Prometheus), testing the entire application stack.

### Location

```
tests/e2e/
├── log-pipeline.spec.sh       # HTTP/Syslog → Redis → ES
├── metrics-pipeline.spec.sh    # HTTP → Redis → Prometheus
└── combined-flow.spec.sh       # Full system with all sources
```

### Execution

```bash
make test-e2e               # All E2E tests
bash tests/e2e/log-pipeline.spec.sh
```

### Example: Complete Log Ingestion Pipeline Test

```bash
#!/bin/bash
# tests/e2e/log-pipeline.spec.sh

set -e

LOG_RECEIVER_URL="http://localhost:8081"
AUTH_TOKEN="PENG-DEMO-DEMO-DEMO-DEMO-DEMO"
ES_URL="http://localhost:9200"

echo "Testing complete log ingestion pipeline..."

# 1. Send log via HTTP API
echo "1. Sending test log via HTTP..."
curl -X POST "$LOG_RECEIVER_URL/api/v1/logs" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "service": "test-service",
    "level": "info",
    "message": "E2E test log message"
  }'

echo "✓ Log sent"

# 2. Wait for worker processing
echo "2. Waiting for worker to process..."
sleep 2

# 3. Verify in Elasticsearch
echo "3. Verifying in Elasticsearch..."
ES_RESPONSE=$(curl -s "$ES_URL/logs-*/_search?q=test-service" | jq '.hits.total.value')

if [ "$ES_RESPONSE" -gt 0 ]; then
    echo "✓ Log found in Elasticsearch ($ES_RESPONSE documents)"
    exit 0
else
    echo "✗ Log not found in Elasticsearch"
    exit 1
fi
```

---

## Performance Tests

### Purpose

Performance tests validate throughput, latency, and queue depth under load to ensure workers meet SLA requirements.

### Location

```
tests/performance/
├── log-throughput-test.sh
├── metrics-throughput-test.sh
├── queue-depth-test.sh
└── latency-profile.sh
```

### Execution

```bash
make test-performance
bash tests/performance/log-throughput-test.sh
```

### Example: Log Throughput Test

```bash
#!/bin/bash
# tests/performance/log-throughput-test.sh

set -e

LOG_RECEIVER_URL="http://localhost:8081"
AUTH_TOKEN="PENG-DEMO-DEMO-DEMO-DEMO-DEMO"
NUM_LOGS=10000

echo "Testing log ingestion throughput with $NUM_LOGS logs..."

start_time=$(date +%s%N)

for i in $(seq 1 $NUM_LOGS); do
  curl -s -X POST "$LOG_RECEIVER_URL/api/v1/logs" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
      "service": "perf-test",
      "level": "info",
      "message": "Performance test log '$i'"
    }' > /dev/null &

  # Batch in groups of 100
  if [ $((i % 100)) -eq 0 ]; then
    wait
  fi
done

wait  # Wait for all background jobs

end_time=$(date +%s%N)
duration_ms=$(((end_time - start_time) / 1000000))
throughput=$(echo "scale=2; $NUM_LOGS / ($duration_ms / 1000)" | bc)

echo "✓ Sent $NUM_LOGS logs in ${duration_ms}ms"
echo "✓ Throughput: $throughput logs/sec"

# Expected: >1000 logs/sec for healthy receiver
if (( $(echo "$throughput > 1000" | bc -l) )); then
    echo "✓ Throughput acceptable (>1000 logs/sec)"
    exit 0
else
    echo "✗ Throughput below target (<1000 logs/sec)"
    exit 1
fi
```

---

## Multi-Protocol Testing

### Purpose

Verify that log receivers correctly handle multiple protocols: HTTP REST API, HTTP3/QUIC, and UDP Syslog.

### Test Coverage

```bash
# HTTP REST API (JSON payloads)
curl -X POST http://localhost:8081/api/v1/logs \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2024-01-06T12:00:00Z",...}'

# UDP Syslog (RFC3164 format)
echo "<14>Jan  6 12:00:00 host service: Message" | nc -u localhost 514

# UDP Syslog (RFC5424 format)
echo "<14>2024-01-06T12:00:00Z host service[pid]: Message" | nc -u localhost 514
```

### Example: Multi-Protocol Test

```bash
#!/bin/bash
# tests/smoke/protocols/test-multi-protocol.sh

set -e

echo "Testing multi-protocol log ingestion..."

# Test 1: HTTP/1.1
echo "1. Testing HTTP/1.1..."
HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8081/api/v1/logs \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2024-01-06T12:00:00Z","service":"test","level":"info","message":"HTTP test"}')

[ "$HTTP_RESPONSE" = "202" ] && echo "✓ HTTP/1.1 working" || exit 1

# Test 2: Syslog UDP
echo "2. Testing Syslog/UDP..."
echo "<14>$(date '+%b %d %H:%M:%S') localhost test: Syslog test" | nc -u -w1 localhost 514
echo "✓ Syslog/UDP sent (async verification)"

echo "✓ All protocols functional"
```

---

## Test Execution Order (Pre-Commit)

Follow this order for efficient testing before commits:

1. **Linters** (fast, <1 min)
2. **Security scans** (fast, <1 min)
3. **Secrets check** (fast, <1 min)
4. **Build & Run** (5-10 min)
5. **Smoke tests** (fast, <2 min) ← Gates further testing
6. **Unit tests** (1-2 min)
7. **Integration tests** (2-5 min)
8. **E2E tests** (5-10 min)
9. **Performance tests** (optional, 5+ min)

## CI/CD Integration

All tests run automatically in GitHub Actions:

- **On PR**: Smoke + Unit + Integration tests
- **On main merge**: All tests including E2E
- **Nightly**: Performance + Multi-protocol tests
- **Release**: Full suite + Manual sign-off

See [Workflows](WORKFLOWS.md) for detailed CI/CD configuration.

---

**Last Updated**: 2026-01-06
**Maintained by**: Penguin Tech Inc
