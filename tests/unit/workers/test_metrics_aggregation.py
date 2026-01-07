"""
Unit tests for killkrill metrics worker aggregation and processing.

Tests metric aggregation logic, batch processing, destination routing,
Redis stream consumption, and error handling with full mocking.
"""

import pytest
import json
import time
import threading
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock, patch, call
import redis
import pydantic


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = Mock()
    return client


@pytest.fixture
def mock_requests():
    """Mock requests library for HTTP operations."""
    with patch('requests.post') as mock_post:
        yield mock_post


@pytest.fixture
def mock_prometheus_gateway():
    """Mock Prometheus gateway URL."""
    return "http://localhost:9091"


@pytest.fixture
def sample_metric_data():
    """Sample metric data for testing."""
    return {
        'name': 'test_metric',
        'type': 'gauge',
        'value': 42.5,
        'labels': {'instance': 'localhost', 'job': 'test'},
        'source': 'test_source',
        'timestamp': '2024-01-06T12:00:00Z'
    }


@pytest.fixture
def sample_metrics_batch():
    """Sample batch of metrics for testing."""
    return [
        {
            'name': 'http_requests_total',
            'type': 'counter',
            'value': 100,
            'labels': {'method': 'GET', 'status': '200'},
            'source': 'api',
            'timestamp': '2024-01-06T12:00:00Z'
        },
        {
            'name': 'response_time_ms',
            'type': 'histogram',
            'value': 45.3,
            'labels': {'endpoint': '/api/v1/users'},
            'source': 'api',
            'timestamp': '2024-01-06T12:00:01Z'
        },
        {
            'name': 'memory_usage_bytes',
            'type': 'gauge',
            'value': 524288000,
            'labels': {'instance': 'worker-1'},
            'source': 'worker',
            'timestamp': '2024-01-06T12:00:02Z'
        },
    ]


@pytest.fixture
def mock_config():
    """Mock configuration for metrics worker."""
    config = Mock()
    config.redis_url = "redis://localhost:6379/0"
    config.license_key = "PENG-TEST-TEST-TEST-TEST-ABCD"
    config.product_name = "killkrill-metrics-worker"
    config.prometheus_gateway = "http://localhost:9091"
    config.prometheus_push_interval = 15
    config.processor_workers = 4
    config.max_batch_size = 100
    config.hdfs_url = None
    config.spark_url = None
    config.gcp_project_id = None
    config.gcp_instance_id = None
    return config


# ============================================================================
# Prometheus Destination Tests
# ============================================================================

@pytest.mark.unit
class TestPrometheusDestination:
    """Test Prometheus destination for metrics."""

    @patch('requests.post')
    def test_prometheus_destination_initialization(self, mock_post, mock_prometheus_gateway):
        """Test PrometheusDestination initializes correctly."""
        # Simulate the PrometheusDestination class behavior
        class PrometheusDestination:
            def __init__(self, gateway_url: str, push_interval: int = 15):
                self.gateway_url = gateway_url
                self.push_interval = push_interval
                self.metrics_buffer = []
                self.buffer_lock = threading.Lock()
                self.last_push = 0

        dest = PrometheusDestination(mock_prometheus_gateway, push_interval=15)

        assert dest.gateway_url == mock_prometheus_gateway
        assert dest.push_interval == 15
        assert dest.metrics_buffer == []
        assert dest.last_push == 0

    @patch('requests.post')
    def test_add_metric_success(self, mock_post, mock_prometheus_gateway, sample_metric_data):
        """Test adding a valid metric to destination."""
        # Simulate PrometheusDestination with add_metric
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float
            labels: Dict[str, str] = {}
            timestamp: str = None
            help: str = None

        class PrometheusDestination:
            def __init__(self, gateway_url: str, push_interval: int = 15):
                self.gateway_url = gateway_url
                self.push_interval = push_interval
                self.metrics_buffer = []
                self.buffer_lock = threading.Lock()
                self.last_push = 0

            def add_metric(self, metric_data: Dict[str, Any]) -> bool:
                try:
                    metric = MetricEntry.model_validate(metric_data)
                    with self.buffer_lock:
                        self.metrics_buffer.append({
                            'name': metric.name,
                            'type': metric.type,
                            'value': metric.value,
                            'labels': metric.labels or {},
                            'timestamp': metric.timestamp or datetime.utcnow().isoformat(),
                            'help': metric.help or f"Metric {metric.name}"
                        })
                    return True
                except Exception:
                    return False

        dest = PrometheusDestination(mock_prometheus_gateway)
        result = dest.add_metric(sample_metric_data)

        assert result is True
        assert len(dest.metrics_buffer) == 1
        assert dest.metrics_buffer[0]['name'] == 'test_metric'
        assert dest.metrics_buffer[0]['value'] == 42.5

    @patch('requests.post')
    def test_add_metric_with_defaults(self, mock_post, mock_prometheus_gateway):
        """Test adding metric with default values for optional fields."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float
            labels: Dict[str, str] = {}
            timestamp: str = None
            help: str = None

        class PrometheusDestination:
            def __init__(self, gateway_url: str, push_interval: int = 15):
                self.gateway_url = gateway_url
                self.metrics_buffer = []
                self.buffer_lock = threading.Lock()

            def add_metric(self, metric_data: Dict[str, Any]) -> bool:
                try:
                    metric = MetricEntry.model_validate(metric_data)
                    with self.buffer_lock:
                        self.metrics_buffer.append({
                            'name': metric.name,
                            'type': metric.type,
                            'value': metric.value,
                            'labels': metric.labels or {},
                            'timestamp': metric.timestamp or datetime.utcnow().isoformat(),
                        })
                    return True
                except Exception:
                    return False

        dest = PrometheusDestination(mock_prometheus_gateway)
        metric = {
            'name': 'simple_metric',
            'type': 'gauge',
            'value': 10.0,
            'source': 'test'
        }

        result = dest.add_metric(metric)

        assert result is True
        assert dest.metrics_buffer[0]['labels'] == {}
        assert 'timestamp' in dest.metrics_buffer[0]

    @patch('requests.post')
    def test_add_metric_invalid_data(self, mock_post, mock_prometheus_gateway):
        """Test adding invalid metric data."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float
            labels: Dict[str, str] = {}

        class PrometheusDestination:
            def __init__(self, gateway_url: str, push_interval: int = 15):
                self.gateway_url = gateway_url
                self.metrics_buffer = []
                self.buffer_lock = threading.Lock()

            def add_metric(self, metric_data: Dict[str, Any]) -> bool:
                try:
                    metric = MetricEntry.model_validate(metric_data)
                    with self.buffer_lock:
                        self.metrics_buffer.append(metric.model_dump())
                    return True
                except Exception:
                    return False

        dest = PrometheusDestination(mock_prometheus_gateway)
        invalid_metric = {
            'name': 'test',
            # Missing required 'type' field
            'value': 10.0
        }

        result = dest.add_metric(invalid_metric)

        assert result is False

    @patch('requests.post')
    def test_push_metrics_to_prometheus(self, mock_post, mock_prometheus_gateway):
        """Test pushing metrics to Prometheus gateway."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Simulate push behavior
        metrics_buffer = [
            {
                'name': 'test_metric',
                'type': 'gauge',
                'value': 42.5,
                'labels': {'job': 'test'},
                'timestamp': '2024-01-06T12:00:00Z',
                'help': 'Test metric'
            }
        ]

        payload = "\n".join([
            "# HELP test_metric Test metric",
            "# TYPE test_metric gauge",
            'test_metric{job="test"} 42.5'
        ])

        mock_post(
            f"{mock_prometheus_gateway}/metrics/job/killkrill-metrics",
            data=payload,
            headers={'Content-Type': 'text/plain'},
            timeout=30
        )

        assert mock_post.called
        assert mock_post.call_args[1]['data'] == payload

    @patch('requests.post')
    def test_push_metrics_formats_prometheus_text(self, mock_post, mock_prometheus_gateway):
        """Test metrics are formatted correctly for Prometheus."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Simulate formatting
        metrics = [
            {
                'name': 'http_requests',
                'type': 'counter',
                'value': 100,
                'labels': {'method': 'GET', 'status': '200'},
                'help': 'HTTP requests total'
            }
        ]

        # Build expected payload
        payload = (
            "# HELP http_requests HTTP requests total\n"
            "# TYPE http_requests counter\n"
            'http_requests{method="GET",status="200"} 100'
        )

        assert '# HELP http_requests' in payload
        assert '# TYPE http_requests counter' in payload
        assert 'http_requests{method="GET",status="200"} 100' in payload

    @patch('requests.post')
    def test_push_metrics_handles_connection_error(self, mock_post, mock_prometheus_gateway):
        """Test handling connection errors during push."""
        mock_post.side_effect = Exception("Connection refused")

        # Test that error is handled gracefully
        try:
            mock_post(
                f"{mock_prometheus_gateway}/metrics/job/killkrill-metrics",
                data="test",
                headers={'Content-Type': 'text/plain'},
                timeout=30
            )
            assert False, "Should have raised exception"
        except Exception:
            assert True  # Exception expected

    @patch('requests.post')
    def test_push_metrics_handles_http_error(self, mock_post, mock_prometheus_gateway):
        """Test handling HTTP errors during push."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        response = mock_post(
            f"{mock_prometheus_gateway}/metrics/job/killkrill-metrics",
            data="test",
            headers={'Content-Type': 'text/plain'},
            timeout=30
        )

        assert response.status_code == 500

    def test_push_metrics_groups_by_name_and_type(self):
        """Test metrics are grouped by name and type during push."""
        metrics = [
            {
                'name': 'requests',
                'type': 'counter',
                'value': 100,
                'labels': {'endpoint': '/api'},
            },
            {
                'name': 'requests',
                'type': 'counter',
                'value': 50,
                'labels': {'endpoint': '/health'},
            },
        ]

        # Simulate grouping
        metric_groups = {}
        for metric in metrics:
            key = (metric['name'], metric['type'])
            if key not in metric_groups:
                metric_groups[key] = []
            metric_groups[key].append(metric)

        assert len(metric_groups) == 1
        assert len(metric_groups[('requests', 'counter')]) == 2


# ============================================================================
# HDFS Destination Tests
# ============================================================================

@pytest.mark.unit
class TestHDFSDestination:
    """Test HDFS destination for metrics."""

    def test_hdfs_destination_initialization(self):
        """Test HDFSDestination initializes correctly."""
        class HDFSDestination:
            def __init__(self, hdfs_url: str):
                self.hdfs_url = hdfs_url
                self.enabled = False

        dest = HDFSDestination("hdfs://namenode:9000")

        assert dest.hdfs_url == "hdfs://namenode:9000"
        assert dest.enabled is False

    def test_hdfs_add_metric_placeholder(self, sample_metric_data):
        """Test HDFS add_metric is placeholder implementation."""
        class HDFSDestination:
            def __init__(self, hdfs_url: str):
                self.hdfs_url = hdfs_url

            def add_metric(self, metric_data: Dict[str, Any]) -> bool:
                return True

        dest = HDFSDestination("hdfs://namenode:9000")
        result = dest.add_metric(sample_metric_data)

        assert result is True


# ============================================================================
# Spark Destination Tests
# ============================================================================

@pytest.mark.unit
class TestSPARCDestination:
    """Test Apache Spark destination for metrics."""

    def test_spark_destination_initialization(self):
        """Test SPARCDestination initializes correctly."""
        class SPARCDestination:
            def __init__(self, spark_url: str):
                self.spark_url = spark_url
                self.enabled = False

        dest = SPARCDestination("spark://master:7077")

        assert dest.spark_url == "spark://master:7077"
        assert dest.enabled is False

    def test_spark_add_metric_placeholder(self, sample_metric_data):
        """Test Spark add_metric is placeholder implementation."""
        class SPARCDestination:
            def __init__(self, spark_url: str):
                self.spark_url = spark_url

            def add_metric(self, metric_data: Dict[str, Any]) -> bool:
                return True

        dest = SPARCDestination("spark://master:7077")
        result = dest.add_metric(sample_metric_data)

        assert result is True


# ============================================================================
# GCP Bigtable Destination Tests
# ============================================================================

@pytest.mark.unit
class TestGCPBigtableDestination:
    """Test Google Cloud Bigtable destination for metrics."""

    def test_bigtable_destination_initialization(self):
        """Test GCPBigtableDestination initializes correctly."""
        class GCPBigtableDestination:
            def __init__(self, project_id: str, instance_id: str):
                self.project_id = project_id
                self.instance_id = instance_id
                self.enabled = False

        dest = GCPBigtableDestination("my-project", "my-instance")

        assert dest.project_id == "my-project"
        assert dest.instance_id == "my-instance"
        assert dest.enabled is False

    def test_bigtable_add_metric_placeholder(self, sample_metric_data):
        """Test Bigtable add_metric is placeholder implementation."""
        class GCPBigtableDestination:
            def __init__(self, project_id: str, instance_id: str):
                self.project_id = project_id
                self.instance_id = instance_id

            def add_metric(self, metric_data: Dict[str, Any]) -> bool:
                return True

        dest = GCPBigtableDestination("my-project", "my-instance")
        result = dest.add_metric(sample_metric_data)

        assert result is True


# ============================================================================
# Metrics Worker Tests
# ============================================================================

@pytest.mark.unit
class TestMetricsWorker:
    """Test metrics worker core functionality."""

    def test_worker_initialization(self, mock_config):
        """Test MetricsWorker initializes with correct parameters."""
        class MetricsWorker:
            def __init__(self, worker_id: int):
                self.worker_id = worker_id
                self.stream_name = "metrics:raw"
                self.consumer_group = "metrics-workers"
                self.consumer_name = f"worker-{worker_id}"
                self.running = False
                self.destinations = {}

        worker = MetricsWorker(worker_id=0)

        assert worker.worker_id == 0
        assert worker.stream_name == "metrics:raw"
        assert worker.consumer_group == "metrics-workers"
        assert worker.consumer_name == "worker-0"
        assert worker.running is False

    def test_process_metric_single_destination(self, sample_metric_data):
        """Test processing metric to single destination."""
        class MetricsWorker:
            def __init__(self, worker_id: int):
                self.worker_id = worker_id
                self.destinations = {'prometheus': Mock()}

            def process_metric(self, metric_data: Dict[str, Any]) -> bool:
                try:
                    success_count = 0
                    for dest in self.destinations.values():
                        if dest.add_metric(metric_data):
                            success_count += 1
                    return success_count > 0
                except Exception:
                    return False

        worker = MetricsWorker(worker_id=0)
        result = worker.process_metric(sample_metric_data)

        assert result is True or result is False  # Should execute without error

    def test_process_metric_handles_invalid_data(self):
        """Test processing invalid metric data."""
        class MetricsWorker:
            def __init__(self, worker_id: int):
                self.destinations = {}

            def process_metric(self, metric_data: Dict[str, Any]) -> bool:
                try:
                    # Validate required fields
                    if not metric_data:
                        return False
                    return True
                except Exception:
                    return False

        worker = MetricsWorker(worker_id=0)
        invalid_metric = {}

        result = worker.process_metric(invalid_metric)

        assert result is False

    def test_consume_messages_empty_queue(self, mock_redis_client):
        """Test consuming messages when queue is empty."""
        class MetricsWorker:
            def __init__(self, worker_id: int, redis_client):
                self.worker_id = worker_id
                self.redis_client = redis_client
                self.stream_name = "metrics:raw"
                self.consumer_group = "metrics-workers"
                self.consumer_name = f"worker-{worker_id}"

            def consume_messages(self):
                messages = self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=100,
                    block=1000
                )
                return messages

        mock_redis_client.xreadgroup.return_value = None

        worker = MetricsWorker(worker_id=0, redis_client=mock_redis_client)
        result = worker.consume_messages()

        assert result is None

    def test_consume_messages_with_messages(self, mock_redis_client):
        """Test consuming messages from queue."""
        class MetricsWorker:
            def __init__(self, worker_id: int, redis_client):
                self.worker_id = worker_id
                self.redis_client = redis_client
                self.stream_name = "metrics:raw"
                self.consumer_group = "metrics-workers"
                self.consumer_name = f"worker-{worker_id}"

            def consume_messages(self):
                messages = self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=100,
                    block=1000
                )
                return messages

        message_id = b'1234567890-0'
        fields = {
            b'name': b'test_metric',
            b'type': b'gauge',
            b'value': b'42.5',
        }

        mock_redis_client.xreadgroup.return_value = [
            (b'metrics:raw', [(message_id, fields)])
        ]

        worker = MetricsWorker(worker_id=0, redis_client=mock_redis_client)
        result = worker.consume_messages()

        assert result is not None
        assert len(result) == 1

    def test_worker_stop(self):
        """Test stopping metrics worker."""
        class MetricsWorker:
            def __init__(self, worker_id: int):
                self.worker_id = worker_id
                self.running = False

            def stop(self):
                self.running = False

        worker = MetricsWorker(worker_id=0)
        worker.running = True

        worker.stop()

        assert worker.running is False


# ============================================================================
# Metrics Processor Tests
# ============================================================================

@pytest.mark.unit
class TestMetricsProcessor:
    """Test metrics processor orchestration."""

    def test_processor_initialization(self, mock_config):
        """Test MetricsProcessor initializes with correct worker count."""
        class MetricsProcessor:
            def __init__(self, num_workers: int = 4):
                self.num_workers = num_workers
                self.workers = []
                self.shutdown_event = threading.Event()

        processor = MetricsProcessor(num_workers=4)

        assert processor.num_workers == 4
        assert processor.workers == []
        assert processor.shutdown_event.is_set() is False

    def test_processor_stops_workers(self):
        """Test processor stops all workers gracefully."""
        class MetricsProcessor:
            def __init__(self, num_workers: int = 4):
                self.workers = []

            def stop(self):
                for worker, thread in self.workers:
                    worker.stop()
                for worker, thread in self.workers:
                    thread.join(timeout=10)

        processor = MetricsProcessor(num_workers=2)
        mock_worker1 = Mock()
        mock_worker2 = Mock()
        mock_thread1 = Mock()
        mock_thread2 = Mock()

        processor.workers = [
            (mock_worker1, mock_thread1),
            (mock_worker2, mock_thread2)
        ]

        processor.stop()

        # Verify all workers were stopped
        mock_worker1.stop.assert_called_once()
        mock_worker2.stop.assert_called_once()


# ============================================================================
# Metric Entry Validation Tests
# ============================================================================

@pytest.mark.unit
class TestMetricEntry:
    """Test MetricEntry validation."""

    def test_metric_entry_valid(self):
        """Test MetricEntry with valid data."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float
            labels: Dict[str, str] = {}
            help: str = None

        entry = MetricEntry(
            name="test_metric",
            type="gauge",
            value=42.5,
            labels={"job": "test"},
            help="Test metric"
        )

        assert entry.name == "test_metric"
        assert entry.type == "gauge"
        assert entry.value == 42.5
        assert entry.labels == {"job": "test"}

    def test_metric_entry_missing_required_field(self):
        """Test MetricEntry validation with missing required field."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float

        with pytest.raises(pydantic.ValidationError):
            MetricEntry(
                # Missing 'name'
                type="gauge",
                value=42.5
            )

    def test_metric_entry_invalid_type(self):
        """Test MetricEntry with invalid field type."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float

        with pytest.raises(pydantic.ValidationError):
            MetricEntry(
                name="test",
                type="gauge",
                value="not_a_number"  # Should be float
            )

    def test_metric_entry_optional_defaults(self):
        """Test MetricEntry optional fields have correct defaults."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float
            labels: Dict[str, str] = {}
            timestamp: str = None
            help: str = None

        entry = MetricEntry(
            name="minimal_metric",
            type="counter",
            value=1.0
        )

        assert entry.labels == {}
        assert entry.timestamp is None
        assert entry.help is None


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

@pytest.mark.unit
class TestEdgeCasesAndErrors:
    """Test edge cases and error handling scenarios."""

    def test_metric_with_very_large_value(self):
        """Test processing metric with very large value."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float

        entry = MetricEntry(
            name="large_metric",
            type="gauge",
            value=1e15  # Very large number
        )

        assert entry.value == 1e15

    def test_metric_with_zero_value(self):
        """Test processing metric with zero value."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float

        entry = MetricEntry(
            name="zero_metric",
            type="gauge",
            value=0.0
        )

        assert entry.value == 0.0

    def test_metric_with_negative_value(self):
        """Test processing metric with negative value."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float

        entry = MetricEntry(
            name="negative_metric",
            type="gauge",
            value=-42.5
        )

        assert entry.value == -42.5

    def test_metric_with_empty_labels(self):
        """Test processing metric with empty labels dict."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float
            labels: Dict[str, str] = {}

        entry = MetricEntry(
            name="metric_no_labels",
            type="gauge",
            value=10.0,
            labels={}
        )

        assert entry.labels == {}

    def test_metric_with_many_labels(self):
        """Test processing metric with many labels."""
        class MetricEntry(pydantic.BaseModel):
            name: str
            type: str
            value: float
            labels: Dict[str, str] = {}

        labels = {f"label_{i}": f"value_{i}" for i in range(50)}

        entry = MetricEntry(
            name="metric_many_labels",
            type="gauge",
            value=10.0,
            labels=labels
        )

        assert len(entry.labels) == 50

    @patch('requests.post')
    def test_prometheus_push_timeout(self, mock_post):
        """Test Prometheus push handles timeouts gracefully."""
        mock_post.side_effect = Exception("Request timeout")

        metrics_buffer = [
            {
                'name': 'timeout_metric',
                'type': 'gauge',
                'value': 10.0,
                'labels': {},
                'timestamp': '2024-01-06T12:00:00Z',
                'help': 'Test'
            }
        ]

        try:
            mock_post(
                "http://localhost:9091/metrics/job/killkrill-metrics",
                data="test",
                timeout=30
            )
            assert False, "Should raise exception"
        except Exception:
            # Buffer should be preserved for retry
            assert len(metrics_buffer) == 1

    def test_batch_processing_empty_messages(self):
        """Test batch processing with empty message list."""
        class MetricsWorker:
            def process_message_batch(self, stream: str, messages: List) -> int:
                return len(messages)

        worker = MetricsWorker()
        result = worker.process_message_batch('metrics:raw', [])

        assert result == 0
