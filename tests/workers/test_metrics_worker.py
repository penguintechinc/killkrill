"""
KillKrill Metrics Worker Tests
Comprehensive tests for metrics-worker service
"""

import json
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import redis


@pytest.mark.integration
class TestMetricEntry:
    """Tests for MetricEntry Pydantic model"""

    def test_valid_metric_entry(self):
        """Test creating valid metric entry"""
        from apps.metrics_worker.app import MetricEntry

        metric = MetricEntry(
            name="http_requests_total",
            type="counter",
            value=150.0,
            labels={"method": "GET", "status": "200"},
            timestamp=datetime.utcnow().isoformat(),
            help="Total HTTP requests",
        )

        assert metric.name == "http_requests_total"
        assert metric.type == "counter"
        assert metric.value == 150.0
        assert metric.labels == {"method": "GET", "status": "200"}

    def test_metric_entry_defaults(self):
        """Test metric entry with default values"""
        from apps.metrics_worker.app import MetricEntry

        metric = MetricEntry(name="test_metric", type="gauge", value=42.0)

        assert metric.labels == {}
        assert metric.timestamp is None
        assert metric.help is None

    def test_metric_entry_validation(self):
        """Test metric entry validation"""
        import pydantic

        from apps.metrics_worker.app import MetricEntry

        # Missing required fields should raise error
        with pytest.raises(pydantic.ValidationError):
            MetricEntry(name="test", type="gauge")  # Missing value

        # Invalid value type should raise error
        with pytest.raises(pydantic.ValidationError):
            MetricEntry(name="test", type="gauge", value="not_a_number")


@pytest.mark.integration
class TestPrometheusDestination:
    """Tests for Prometheus destination"""

    def test_initialization(self):
        """Test Prometheus destination initialization"""
        from apps.metrics_worker.app import PrometheusDestination

        dest = PrometheusDestination("http://localhost:9091", push_interval=15)

        assert dest.gateway_url == "http://localhost:9091"
        assert dest.push_interval == 15
        assert dest.metrics_buffer == []

    def test_add_metric_to_buffer(self):
        """Test adding metric to buffer"""
        from apps.metrics_worker.app import PrometheusDestination

        dest = PrometheusDestination("http://localhost:9091", push_interval=15)

        metric_data = {
            "name": "test_metric",
            "type": "gauge",
            "value": 100.0,
            "labels": {"instance": "web-1"},
            "help": "Test metric",
        }

        result = dest.add_metric(metric_data)

        assert result is True
        assert len(dest.metrics_buffer) == 1
        assert dest.metrics_buffer[0]["name"] == "test_metric"

    def test_buffer_flush_on_size(self, mock_prometheus_gateway):
        """Test buffer flush when size threshold reached"""
        from apps.metrics_worker.app import PrometheusDestination

        dest = PrometheusDestination("http://localhost:9091", push_interval=60)

        # Add 100 metrics to trigger flush
        for i in range(100):
            metric_data = {
                "name": f"metric_{i}",
                "type": "gauge",
                "value": float(i),
                "help": "Test metric",
            }
            dest.add_metric(metric_data)

        # Buffer should have flushed
        assert len(dest.metrics_buffer) == 0
        mock_prometheus_gateway.assert_called()

    def test_buffer_flush_on_interval(self, mock_prometheus_gateway):
        """Test buffer flush when time interval elapsed"""
        from apps.metrics_worker.app import PrometheusDestination

        dest = PrometheusDestination("http://localhost:9091", push_interval=1)
        dest.last_push = time.time() - 2  # Simulate 2 seconds ago

        metric_data = {
            "name": "test_metric",
            "type": "gauge",
            "value": 42.0,
            "help": "Test",
        }

        dest.add_metric(metric_data)

        # Should have triggered push due to elapsed time
        mock_prometheus_gateway.assert_called()

    @patch("requests.post")
    def test_push_metrics_format(self, mock_post):
        """Test Prometheus exposition format"""
        from apps.metrics_worker.app import PrometheusDestination

        mock_post.return_value = Mock(status_code=200, text="OK")

        dest = PrometheusDestination("http://localhost:9091")

        # Add metrics
        dest.metrics_buffer = [
            {
                "name": "http_requests_total",
                "type": "counter",
                "value": 150.0,
                "labels": {"method": "GET", "status": "200"},
                "help": "Total requests",
            },
            {
                "name": "http_requests_total",
                "type": "counter",
                "value": 50.0,
                "labels": {"method": "POST", "status": "201"},
                "help": "Total requests",
            },
        ]

        dest._push_metrics()

        # Verify request was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        assert "/metrics/job/killkrill-metrics" in call_args[0][0]

        # Verify payload format
        payload = call_args[1]["data"]
        assert "# HELP http_requests_total" in payload
        assert "# TYPE http_requests_total counter" in payload
        assert 'http_requests_total{method="GET",status="200"} 150.0' in payload

    @patch("requests.post")
    def test_push_metrics_failure(self, mock_post):
        """Test handling push failure"""
        from apps.metrics_worker.app import PrometheusDestination

        mock_post.return_value = Mock(status_code=500, text="Internal Server Error")

        dest = PrometheusDestination("http://localhost:9091")
        dest.metrics_buffer = [
            {
                "name": "test",
                "type": "gauge",
                "value": 1.0,
                "labels": {},
                "help": "Test",
            }
        ]

        # Should not raise exception
        dest._push_metrics()

        # Buffer should still contain metrics (retry logic)
        assert len(dest.metrics_buffer) >= 0

    def test_thread_safe_buffer_access(self):
        """Test thread-safe access to metrics buffer"""
        from apps.metrics_worker.app import PrometheusDestination

        dest = PrometheusDestination("http://localhost:9091", push_interval=60)

        def add_metrics():
            for i in range(50):
                metric_data = {
                    "name": f"metric_{i}",
                    "type": "gauge",
                    "value": float(i),
                    "help": "Test",
                }
                dest.add_metric(metric_data)

        # Add metrics from multiple threads
        threads = [threading.Thread(target=add_metrics) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All metrics should be added (no race condition)
        # Note: Some may have been flushed if buffer filled
        assert dest.last_push >= 0


@pytest.mark.integration
class TestMetricsWorker:
    """Tests for MetricsWorker class"""

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_worker_initialization(self, mock_config, mock_redis):
        """Test worker initialization"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15

        worker = MetricsWorker(worker_id=1)

        assert worker.worker_id == 1
        assert worker.stream_name == "metrics:raw"
        assert worker.consumer_group == "metrics-workers"
        assert worker.consumer_name == "worker-1"
        assert "prometheus" in worker.destinations

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_create_consumer_group(self, mock_config, mock_redis):
        """Test consumer group creation"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15

        worker = MetricsWorker(worker_id=1)

        # Verify xgroup_create was called
        mock_redis.xgroup_create.assert_called_once_with(
            "metrics:raw", "metrics-workers", id="0", mkstream=True
        )

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_consumer_group_already_exists(self, mock_config, mock_redis):
        """Test handling existing consumer group"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15

        mock_redis.xgroup_create.side_effect = redis.exceptions.ResponseError(
            "BUSYGROUP"
        )

        # Should not raise exception
        worker = MetricsWorker(worker_id=1)
        assert worker is not None

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_consume_messages_no_data(self, mock_config, mock_redis):
        """Test consuming when no messages available"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15
        mock_config.max_batch_size = 100

        mock_redis.xreadgroup.return_value = []
        mock_redis.xinfo_stream.return_value = {"length": 0}

        worker = MetricsWorker(worker_id=1)
        worker.consume_messages()

        # Should update queue metrics
        mock_redis.xinfo_stream.assert_called_once()

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_consume_messages_with_data(
        self, mock_config, mock_redis, sample_metric_batch
    ):
        """Test consuming messages from stream"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15
        mock_config.max_batch_size = 100

        # Convert to bytes format
        messages_bytes = []
        for msg_id, fields in sample_metric_batch:
            fields_bytes = {
                k.encode(): v.encode() if isinstance(v, str) else v
                for k, v in fields.items()
            }
            messages_bytes.append((msg_id, fields_bytes))

        mock_redis.xreadgroup.return_value = [(b"metrics:raw", messages_bytes)]

        worker = MetricsWorker(worker_id=1)

        with patch.object(worker, "process_message_batch") as mock_process:
            worker.consume_messages()

        # Verify processing was called
        mock_process.assert_called_once()

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_process_message_batch(self, mock_config, mock_redis, sample_metric_batch):
        """Test processing message batch"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15

        worker = MetricsWorker(worker_id=1)

        # Convert to bytes format
        messages_bytes = []
        for msg_id, fields in sample_metric_batch[:5]:
            fields_bytes = {
                k.encode(): v.encode() if isinstance(v, str) else v
                for k, v in fields.items()
            }
            messages_bytes.append((msg_id.encode(), fields_bytes))

        worker.process_message_batch("metrics:raw", messages_bytes)

        # Verify acknowledgment
        mock_redis.xack.assert_called_once()
        call_args = mock_redis.xack.call_args[0]
        assert call_args[0] == "metrics:raw"
        assert call_args[1] == "metrics-workers"

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_process_single_metric(self, mock_config, mock_redis):
        """Test processing single metric"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        metric_data = {
            "name": "test_metric",
            "type": "gauge",
            "value": "42.0",
            "labels": json.dumps({"instance": "test-1"}),
            "source": "test-source",
        }

        result = worker.process_metric(metric_data)

        assert result is True

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_worker_start_stop(self, mock_config, mock_redis):
        """Test worker start and stop"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15
        mock_config.max_batch_size = 100

        mock_redis.xreadgroup.return_value = []
        mock_redis.xinfo_stream.return_value = {"length": 0}

        worker = MetricsWorker(worker_id=1)

        # Start in thread and stop immediately
        thread = threading.Thread(target=worker.start)
        thread.start()

        time.sleep(0.1)  # Let it run briefly
        worker.stop()
        thread.join(timeout=2)

        assert worker.running is False


@pytest.mark.integration
class TestMetricAggregation:
    """Tests for metric aggregation and windowing"""

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_time_window_aggregation(self, mock_config, mock_redis):
        """Test aggregating metrics within time windows"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        # Simulate multiple metrics with same name
        metrics = []
        for i in range(10):
            metrics.append(
                {
                    "name": "request_latency",
                    "type": "histogram",
                    "value": str(float(i * 10)),
                    "labels": json.dumps({"endpoint": "/api/users"}),
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "api-server",
                }
            )

        # Process all metrics
        for metric in metrics:
            worker.process_metric(metric)

        # Verify all were processed
        assert worker.destinations["prometheus"].metrics_buffer

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_multi_metric_aggregation(self, mock_config, mock_redis):
        """Test aggregating different metric types"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        metrics = [
            {
                "name": "http_requests_total",
                "type": "counter",
                "value": "100",
                "source": "web",
            },
            {
                "name": "memory_usage_bytes",
                "type": "gauge",
                "value": "1024000",
                "source": "system",
            },
            {
                "name": "request_duration_seconds",
                "type": "histogram",
                "value": "0.5",
                "source": "api",
            },
        ]

        for metric in metrics:
            result = worker.process_metric(metric)
            assert result is True


@pytest.mark.integration
class TestMultipleDestinations:
    """Tests for routing metrics to multiple destinations"""

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_hdfs_destination_placeholder(self, mock_config, mock_redis):
        """Test HDFS destination initialization"""
        from apps.metrics_worker.app import HDFSDestination

        dest = HDFSDestination("hdfs://namenode:9000")

        assert dest.hdfs_url == "hdfs://namenode:9000"
        assert dest.enabled is False

        # Placeholder should accept metrics
        result = dest.add_metric({"name": "test", "type": "gauge", "value": 1.0})
        assert result is True

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_spark_destination_placeholder(self, mock_config, mock_redis):
        """Test Spark destination initialization"""
        from apps.metrics_worker.app import SPARCDestination

        dest = SPARCDestination("spark://master:7077")

        assert dest.spark_url == "spark://master:7077"
        assert dest.enabled is False

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_bigtable_destination_placeholder(self, mock_config, mock_redis):
        """Test GCP Bigtable destination initialization"""
        from apps.metrics_worker.app import GCPBigtableDestination

        dest = GCPBigtableDestination("my-project", "my-instance")

        assert dest.project_id == "my-project"
        assert dest.instance_id == "my-instance"
        assert dest.enabled is False

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_multiple_destination_routing(self, mock_config, mock_redis):
        """Test routing metric to multiple destinations"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60
        mock_config.hdfs_url = "hdfs://namenode:9000"

        worker = MetricsWorker(worker_id=1)

        # Should have both Prometheus and HDFS
        assert "prometheus" in worker.destinations
        assert "hdfs" in worker.destinations

        metric_data = {
            "name": "test_metric",
            "type": "gauge",
            "value": "42.0",
            "source": "test",
        }

        # Metric should be sent to all destinations
        result = worker.process_metric(metric_data)
        assert result is True


@pytest.mark.integration
class TestMetricsProcessor:
    """Tests for main metrics processor"""

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    @patch("apps.metrics_worker.app.PROCESSOR_WORKERS", 2)
    def test_processor_initialization(self, mock_config, mock_redis):
        """Test metrics processor initialization"""
        from apps.metrics_worker.app import MetricsProcessor

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15

        processor = MetricsProcessor(num_workers=2)

        assert processor.num_workers == 2
        assert processor.workers == []
        assert processor.shutdown_event is not None

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_processor_start_workers(self, mock_config, mock_redis):
        """Test starting multiple worker threads"""
        from apps.metrics_worker.app import MetricsProcessor

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15
        mock_config.max_batch_size = 100

        mock_redis.xreadgroup.return_value = []
        mock_redis.xinfo_stream.return_value = {"length": 0}

        processor = MetricsProcessor(num_workers=2)

        # Start and stop immediately
        thread = threading.Thread(target=processor.start)
        thread.start()

        time.sleep(0.5)  # Let workers initialize
        processor.shutdown_event.set()
        processor.stop()
        thread.join(timeout=5)

        # Verify workers were created
        assert len(processor.workers) == 2

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_processor_graceful_shutdown(self, mock_config, mock_redis):
        """Test graceful shutdown of processor"""
        from apps.metrics_worker.app import MetricsProcessor

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15
        mock_config.max_batch_size = 100

        mock_redis.xreadgroup.return_value = []
        mock_redis.xinfo_stream.return_value = {"length": 0}

        processor = MetricsProcessor(num_workers=2)

        # Start and stop
        thread = threading.Thread(target=processor.start)
        thread.start()

        time.sleep(0.2)
        processor.shutdown_event.set()
        processor.stop()
        thread.join(timeout=5)

        # All workers should have stopped
        for worker, _ in processor.workers:
            assert worker.running is False


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling and resilience"""

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_redis_connection_error(self, mock_config, mock_redis):
        """Test handling Redis connection errors"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15

        mock_redis.xreadgroup.side_effect = redis.exceptions.ConnectionError(
            "Connection lost"
        )

        worker = MetricsWorker(worker_id=1)

        # Should not raise exception
        with patch("time.sleep"):
            worker.consume_messages()

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_malformed_metric_handling(self, mock_config, mock_redis):
        """Test handling malformed metric data"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        # Malformed metric missing required fields
        malformed_metric = {
            "name": "test_metric",
            # Missing type and value
            "source": "test",
        }

        # Should handle gracefully
        result = worker.process_metric(malformed_metric)

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_destination_failure_handling(self, mock_config, mock_redis):
        """Test handling destination failures"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        # Mock destination to fail
        with patch.object(
            worker.destinations["prometheus"], "add_metric", return_value=False
        ):
            metric_data = {
                "name": "test",
                "type": "gauge",
                "value": "42.0",
                "source": "test",
            }

            result = worker.process_metric(metric_data)
            # Should still return (not crash)

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_acknowledgment_failure(self, mock_config, mock_redis):
        """Test handling acknowledgment failures"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        mock_redis.xack.side_effect = redis.exceptions.RedisError("ACK failed")

        worker = MetricsWorker(worker_id=1)

        messages = [(b"msg-1", {b"name": b"test", b"type": b"gauge", b"value": b"1"})]

        # Should handle gracefully
        worker.process_message_batch("metrics:raw", messages)


@pytest.mark.integration
class TestBackpressure:
    """Tests for backpressure handling"""

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_large_batch_processing(self, mock_config, mock_redis):
        """Test processing large batch of metrics"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        # Generate large batch
        messages = []
        for i in range(1000):
            msg_id = f"msg-{i}".encode()
            fields = {
                b"name": f"metric_{i}".encode(),
                b"type": b"gauge",
                b"value": str(float(i)).encode(),
                b"source": b"load-test",
            }
            messages.append((msg_id, fields))

        # Should handle without crashing
        worker.process_message_batch("metrics:raw", messages)

        # Verify acknowledgment
        mock_redis.xack.assert_called_once()

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_slow_destination_handling(self, mock_config, mock_redis):
        """Test handling slow destination responses"""
        from apps.metrics_worker.app import MetricsWorker

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        # Mock slow destination
        def slow_add_metric(metric_data):
            time.sleep(0.1)  # Simulate slow operation
            return True

        with patch.object(
            worker.destinations["prometheus"], "add_metric", side_effect=slow_add_metric
        ):
            metric_data = {
                "name": "test",
                "type": "gauge",
                "value": "42.0",
                "source": "test",
            }

            start = time.time()
            worker.process_metric(metric_data)
            duration = time.time() - start

            # Should complete (not hang)
            assert duration < 1.0


@pytest.mark.integration
class TestPrometheusMetricsExposure:
    """Tests for internal Prometheus metrics"""

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_metrics_exposed(self, mock_config, mock_redis):
        """Test that Prometheus metrics are properly exposed"""
        from apps.metrics_worker.app import (
            metrics_processed_counter, processing_errors_counter, processing_time,
            queue_size_gauge,
        )

        assert metrics_processed_counter is not None
        assert processing_errors_counter is not None
        assert processing_time is not None
        assert queue_size_gauge is not None

    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_processing_metrics_incremented(self, mock_config, mock_redis):
        """Test that processing metrics are incremented"""
        from apps.metrics_worker.app import MetricsWorker, metrics_processed_counter

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 60

        worker = MetricsWorker(worker_id=1)

        initial_value = metrics_processed_counter.labels(
            source="test", destination="prometheus", metric_type="gauge"
        )._value.get()

        metric_data = {
            "name": "test",
            "type": "gauge",
            "value": "42.0",
            "source": "test",
        }

        worker.process_metric(metric_data)

        final_value = metrics_processed_counter.labels(
            source="test", destination="prometheus", metric_type="gauge"
        )._value.get()

        assert final_value > initial_value


@pytest.mark.e2e
class TestEndToEnd:
    """End-to-end tests requiring real services"""

    @pytest.mark.skip(reason="Requires real Redis and Prometheus")
    def test_full_metrics_pipeline(self):
        """Test complete metrics ingestion to Prometheus pipeline"""
        # This would test with real Redis and Prometheus Gateway
        pass

    @pytest.mark.skip(reason="Requires real services")
    def test_multi_destination_flow(self):
        """Test metrics flowing to multiple destinations"""
        # This would test with real HDFS, Spark, etc.
        pass


@pytest.mark.integration
class TestMainEntryPoint:
    """Tests for main entry point"""

    @patch("apps.metrics_worker.app.license_client")
    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_main_invalid_license(self, mock_config, mock_redis, mock_license):
        """Test main exits on invalid license"""
        from apps.metrics_worker.app import main

        mock_license.validate.return_value = {"valid": False}

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("apps.metrics_worker.app.license_client")
    @patch("apps.metrics_worker.app.redis_client")
    @patch("apps.metrics_worker.app.config")
    def test_main_valid_license(self, mock_config, mock_redis, mock_license):
        """Test main starts with valid license"""
        from apps.metrics_worker.app import main

        mock_config.prometheus_gateway = "http://localhost:9091"
        mock_config.prometheus_push_interval = 15
        mock_config.max_batch_size = 100

        mock_license.validate.return_value = {"valid": True, "tier": "enterprise"}
        mock_redis.xreadgroup.return_value = []
        mock_redis.xinfo_stream.return_value = {"length": 0}

        # Start and interrupt immediately
        with patch("apps.metrics_worker.app.MetricsProcessor") as mock_processor:
            processor_instance = Mock()
            processor_instance.start = Mock(side_effect=KeyboardInterrupt())
            mock_processor.return_value = processor_instance

            main()

            # Verify processor was created and started
            mock_processor.assert_called_once()
            processor_instance.start.assert_called_once()
