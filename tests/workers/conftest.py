"""
Shared fixtures for worker service tests
"""

import json
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest
import redis


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    client = Mock(spec=redis.Redis)

    # Mock stream operations
    client.xgroup_create = Mock()
    client.xreadgroup = Mock(return_value=[])
    client.xack = Mock()
    client.xpending_range = Mock(return_value=[])
    client.xclaim = Mock(return_value=[])
    client.xinfo_stream = Mock(return_value={"length": 0})
    client.xinfo_groups = Mock(return_value=[])
    client.ping = Mock(return_value=True)

    return client


@pytest.fixture
def mock_elasticsearch_client():
    """Mock Elasticsearch client for testing"""
    client = Mock()
    client.ping = Mock(return_value=True)
    client.bulk = Mock(return_value=(100, []))

    # Mock helpers module
    with patch("elasticsearch.helpers") as mock_helpers:
        mock_helpers.bulk = Mock(return_value=(100, []))
        yield client


@pytest.fixture
def mock_license_client():
    """Mock license client for testing"""
    client = Mock()
    client.validate = Mock(
        return_value={
            "valid": True,
            "tier": "enterprise",
            "features": ["advanced_analytics", "multi_destination"],
        }
    )
    client.keepalive = Mock()
    return client


@pytest.fixture
def sample_log_message():
    """Sample log message for testing"""
    return (
        b"1234567890-0",
        {
            b"timestamp": datetime.utcnow().isoformat().encode(),
            b"log_level": b"info",
            b"message": b"Test log message",
            b"logger_name": b"test.logger",
            b"service_name": b"test-service",
            b"hostname": b"test-host",
            b"source_ip": b"192.168.1.100",
            b"source_id": b"src-001",
            b"protocol": b"syslog",
            b"facility": b"user",
            b"severity": b"info",
            b"program": b"test-app",
            b"application": b"test-service",
            b"raw_log": b"<14>Jan  7 12:00:00 test-host test-app: Test log message",
        },
    )


@pytest.fixture
def sample_log_batch(sample_log_message):
    """Sample batch of log messages"""
    messages = []
    for i in range(10):
        msg_id, fields = sample_log_message
        msg_id = f"{msg_id.decode()}-{i}".encode()
        messages.append((msg_id, fields.copy()))
    return messages


@pytest.fixture
def sample_metric_message():
    """Sample metric message for testing"""
    return (
        b"1234567890-0",
        {
            b"name": b"http_requests_total",
            b"type": b"counter",
            b"value": b"150.0",
            b"labels": json.dumps({"method": "GET", "status": "200"}).encode(),
            b"timestamp": datetime.utcnow().isoformat().encode(),
            b"help": b"Total HTTP requests",
            b"source": b"web-server",
        },
    )


@pytest.fixture
def sample_metric_batch(sample_metric_message):
    """Sample batch of metric messages"""
    messages = []
    metric_types = [b"counter", b"gauge", b"histogram", b"summary"]

    for i in range(20):
        msg_id, fields = sample_metric_message
        msg_id = f"{msg_id.decode()}-{i}".encode()
        fields_copy = fields.copy()
        fields_copy[b"name"] = f"metric_{i}".encode()
        fields_copy[b"type"] = metric_types[i % len(metric_types)]
        fields_copy[b"value"] = str(float(i * 10)).encode()
        messages.append((msg_id, fields_copy))

    return messages


@pytest.fixture
def mock_prometheus_gateway():
    """Mock Prometheus pushgateway"""
    with patch("requests.post") as mock_post:
        mock_post.return_value = Mock(status_code=200, text="OK")
        yield mock_post


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    config = Mock()
    config.redis_url = "redis://localhost:6379"
    config.elasticsearch_hosts = "http://localhost:9200"
    config.elasticsearch_index_prefix = "killkrill-test"
    config.prometheus_gateway = "http://localhost:9091"
    config.prometheus_push_interval = 15
    config.license_key = "test-license-key"
    config.product_name = "killkrill"
    config.processor_workers = 2
    config.max_batch_size = 100
    config.processing_timeout = 30
    return config


@pytest.fixture
def redis_stream_messages():
    """Generate Redis stream messages in correct format"""

    def _generate(count: int, stream_name: str = "logs:raw"):
        """Generate count messages for given stream"""
        messages = []
        for i in range(count):
            msg_id = f"{int(datetime.utcnow().timestamp() * 1000)}-{i}"

            if stream_name == "logs:raw":
                fields = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "log_level": "info",
                    "message": f"Test message {i}",
                    "service_name": "test-service",
                    "hostname": "test-host",
                    "source_id": "src-001",
                }
            else:  # metrics:raw
                fields = {
                    "name": f"test_metric_{i}",
                    "type": "gauge",
                    "value": str(float(i * 10)),
                    "labels": json.dumps({"instance": "test-1"}),
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "test-source",
                }

            messages.append((msg_id, fields))

        return [(stream_name.encode(), messages)]

    return _generate


@pytest.fixture
def pending_messages():
    """Generate pending messages for testing retry logic"""

    def _generate(count: int, idle_time: int = 70000):
        """Generate pending message info"""
        messages = []
        for i in range(count):
            messages.append(
                {
                    "message_id": f"{int(datetime.utcnow().timestamp() * 1000)}-{i}",
                    "consumer": "test-consumer",
                    "time_since_delivered": idle_time,
                    "times_delivered": 1,
                }
            )
        return messages

    return _generate


@pytest.fixture
def elasticsearch_bulk_response():
    """Mock Elasticsearch bulk response"""

    def _generate(success_count: int, failed_count: int = 0):
        """Generate bulk response with given success/failure counts"""
        failed_items = []
        for i in range(failed_count):
            failed_items.append(
                {
                    "index": {
                        "_index": "test-index",
                        "_id": f"failed-{i}",
                        "status": 429,
                        "error": {"type": "too_many_requests", "reason": "Throttled"},
                    }
                }
            )
        return (success_count, failed_items)

    return _generate


@pytest.fixture
def mock_signal_handler():
    """Mock signal handler for testing graceful shutdown"""
    with patch("signal.signal") as mock_signal:
        yield mock_signal


@pytest.fixture
def mock_thread_pool():
    """Mock ThreadPoolExecutor for testing worker threads"""
    with patch("concurrent.futures.ThreadPoolExecutor") as mock_pool:
        pool_instance = Mock()
        pool_instance.submit = Mock()
        pool_instance.shutdown = Mock()
        mock_pool.return_value = pool_instance
        yield mock_pool


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset Prometheus metrics between tests"""
    from prometheus_client import REGISTRY

    # Clear any existing metrics
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass

    yield

    # Cleanup after test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
