"""
KillKrill Log Worker Tests
Comprehensive tests for log-worker service
"""

import hashlib
import json
import time
from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import redis


@pytest.mark.integration
class TestElasticsearchProcessor:
    """Tests for Elasticsearch log processor"""

    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.config")
    def test_process_logs_batch_success(
        self, mock_config, mock_es, sample_log_batch, elasticsearch_bulk_response
    ):
        """Test successful batch processing to Elasticsearch"""
        from apps.log_worker.app import ElasticsearchProcessor

        mock_config.elasticsearch_index_prefix = "killkrill-test"

        with patch(
            "elasticsearch.helpers.bulk",
            return_value=elasticsearch_bulk_response(10, 0),
        ):
            processor = ElasticsearchProcessor()
            result = processor.process_logs_batch(sample_log_batch)

            assert result == 10

    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.config")
    def test_process_logs_batch_partial_failure(
        self, mock_config, mock_es, sample_log_batch, elasticsearch_bulk_response
    ):
        """Test batch processing with partial failures"""
        from apps.log_worker.app import ElasticsearchProcessor

        mock_config.elasticsearch_index_prefix = "killkrill-test"

        # 7 successful, 3 failed
        with patch(
            "elasticsearch.helpers.bulk", return_value=elasticsearch_bulk_response(7, 3)
        ):
            processor = ElasticsearchProcessor()
            result = processor.process_logs_batch(sample_log_batch)

            assert result == 7

    @patch("apps.log-worker.app.config")
    def test_convert_to_ecs_document(self, mock_config, sample_log_message):
        """Test log conversion to ECS-compliant format"""
        from apps.log_worker.app import ElasticsearchProcessor

        mock_config.elasticsearch_index_prefix = "killkrill-test"

        processor = ElasticsearchProcessor()
        msg_id, fields = sample_log_message

        # Decode bytes to strings for processing
        fields_decoded = {
            k.decode(): v.decode() if isinstance(v, bytes) else v
            for k, v in fields.items()
        }

        doc = processor._convert_to_ecs_document(fields_decoded, msg_id.decode())

        assert doc is not None
        assert "@timestamp" in doc["_source"]
        assert doc["_source"]["ecs"]["version"] == "8.0"
        assert doc["_source"]["event"]["dataset"] == "killkrill.logs"
        assert doc["_source"]["log"]["level"] == "info"
        assert doc["_source"]["message"] == "Test log message"
        assert doc["_source"]["service"]["name"] == "test-service"
        assert doc["_source"]["host"]["name"] == "test-host"

        # Verify document ID is hash of message ID
        expected_id = hashlib.sha256(msg_id).hexdigest()
        assert doc["_id"] == expected_id

    @patch("apps.log-worker.app.config")
    def test_ecs_document_with_optional_fields(self, mock_config):
        """Test ECS document creation with optional fields"""
        from apps.log_worker.app import ElasticsearchProcessor

        mock_config.elasticsearch_index_prefix = "killkrill-test"

        processor = ElasticsearchProcessor()

        fields = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Error occurred",
            "log_level": "error",
            "service_name": "test-service",
            "trace_id": "trace-123",
            "span_id": "span-456",
            "transaction_id": "txn-789",
            "error_type": "ValueError",
            "error_message": "Invalid value",
            "error_stack_trace": "Traceback...",
            "labels": json.dumps({"environment": "production", "version": "1.0.0"}),
            "tags": json.dumps(["critical", "payment"]),
        }

        doc = processor._convert_to_ecs_document(fields, "test-msg-id")

        assert doc["_source"]["trace"]["id"] == "trace-123"
        assert doc["_source"]["trace"]["span"]["id"] == "span-456"
        assert doc["_source"]["trace"]["transaction"]["id"] == "txn-789"
        assert doc["_source"]["error"]["type"] == "ValueError"
        assert doc["_source"]["error"]["message"] == "Invalid value"
        assert doc["_source"]["labels"]["environment"] == "production"
        assert "critical" in doc["_source"]["tags"]

    @patch("apps.log-worker.app.config")
    def test_ecs_document_invalid_timestamp(self, mock_config):
        """Test ECS document with invalid timestamp defaults to current time"""
        from apps.log_worker.app import ElasticsearchProcessor

        mock_config.elasticsearch_index_prefix = "killkrill-test"

        processor = ElasticsearchProcessor()

        fields = {
            "timestamp": "invalid-timestamp",
            "message": "Test",
            "service_name": "test",
        }

        doc = processor._convert_to_ecs_document(fields, "test-msg")

        # Should have timestamp even with invalid input
        assert "@timestamp" in doc["_source"]

    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.config")
    def test_process_empty_batch(self, mock_config, mock_es):
        """Test processing empty batch"""
        from apps.log_worker.app import ElasticsearchProcessor

        processor = ElasticsearchProcessor()
        result = processor.process_logs_batch([])

        assert result == 0


@pytest.mark.integration
class TestPrometheusProcessor:
    """Tests for Prometheus metrics processor"""

    @patch("apps.log-worker.app.PROMETHEUS_GATEWAY", "http://localhost:9091")
    def test_process_metrics_batch(self, sample_metric_batch, mock_prometheus_gateway):
        """Test processing metrics batch for Prometheus"""
        from apps.log_worker.app import PrometheusProcessor

        processor = PrometheusProcessor()
        result = processor.process_metrics_batch(sample_metric_batch)

        assert result == len(sample_metric_batch)

    @patch("apps.log-worker.app.PROMETHEUS_GATEWAY", "http://localhost:9091")
    def test_group_metrics_by_source(self, sample_metric_batch):
        """Test metrics grouping by source and type"""
        from apps.log_worker.app import PrometheusProcessor

        processor = PrometheusProcessor()
        groups = processor._group_metrics(sample_metric_batch)

        # Should have groups based on source and metric type
        assert len(groups) > 0

        # Verify group structure
        for group_key, metrics in groups.items():
            assert isinstance(metrics, list)
            assert len(metrics) > 0
            for metric in metrics:
                assert "name" in metric
                assert "value" in metric
                assert "type" in metric

    @patch("apps.log-worker.app.PROMETHEUS_GATEWAY", "http://localhost:9091")
    def test_parse_labels(self):
        """Test label parsing from JSON"""
        from apps.log_worker.app import PrometheusProcessor

        processor = PrometheusProcessor()

        # Test JSON string
        labels_json = json.dumps({"env": "prod", "instance": "web-1"})
        labels = processor._parse_labels(labels_json)
        assert labels == {"env": "prod", "instance": "web-1"}

        # Test dict
        labels_dict = {"env": "dev", "instance": "web-2"}
        labels = processor._parse_labels(labels_dict)
        assert labels == labels_dict

        # Test invalid JSON
        labels = processor._parse_labels("invalid json")
        assert labels == {}

    @patch("apps.log-worker.app.PROMETHEUS_GATEWAY", "http://localhost:9091")
    def test_process_empty_metrics_batch(self):
        """Test processing empty metrics batch"""
        from apps.log_worker.app import PrometheusProcessor

        processor = PrometheusProcessor()
        result = processor.process_metrics_batch([])

        assert result == 0


@pytest.mark.integration
class TestRedisStreamsConsumer:
    """Tests for Redis Streams consumer"""

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.config")
    def test_consumer_initialization(self, mock_config, mock_redis):
        """Test consumer group initialization"""
        from apps.log_worker.app import RedisStreamsConsumer

        mock_config.elasticsearch_index_prefix = "test"

        consumer = RedisStreamsConsumer("logs:raw", "test-group", "test-consumer")

        # Verify consumer group creation was attempted
        mock_redis.xgroup_create.assert_called_once()

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.config")
    def test_consumer_group_already_exists(self, mock_config, mock_redis):
        """Test handling when consumer group already exists"""
        from apps.log_worker.app import RedisStreamsConsumer

        mock_config.elasticsearch_index_prefix = "test"
        mock_redis.xgroup_create.side_effect = redis.ResponseError(
            "BUSYGROUP Consumer Group name already exists"
        )

        # Should not raise exception
        consumer = RedisStreamsConsumer("logs:raw", "test-group", "test-consumer")
        assert consumer is not None

    @patch("apps.log-worker.app.shutdown_requested", False)
    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.config")
    @patch("time.sleep")
    def test_consume_messages_with_data(
        self, mock_sleep, mock_config, mock_es, mock_redis, redis_stream_messages
    ):
        """Test consuming messages from Redis stream"""
        from apps.log_worker.app import RedisStreamsConsumer

        mock_config.elasticsearch_index_prefix = "test"
        mock_config.max_batch_size = 10

        # Setup mock to return messages once then stop
        messages = redis_stream_messages(5, "logs:raw")
        mock_redis.xreadgroup.side_effect = [messages, []]
        mock_redis.xinfo_stream.return_value = {"length": 0}
        mock_redis.xinfo_groups.return_value = [
            {"name": "test-group", "last-delivered-id": "0-0"}
        ]

        # Mock Elasticsearch bulk operation
        with patch("elasticsearch.helpers.bulk", return_value=(5, [])):
            consumer = RedisStreamsConsumer("logs:raw", "test-group", "test-consumer")

            # Run one iteration
            with patch(
                "apps.log-worker.app.shutdown_requested", side_effect=[False, True]
            ):
                consumer.consume_messages()

            # Verify messages were acknowledged
            assert mock_redis.xack.called

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.config")
    def test_process_message_batch(
        self, mock_config, mock_redis, redis_stream_messages
    ):
        """Test processing a batch of messages"""
        from apps.log_worker.app import RedisStreamsConsumer

        mock_config.elasticsearch_index_prefix = "test"

        consumer = RedisStreamsConsumer("logs:raw", "test-group", "test-consumer")

        # Generate test messages
        stream_messages = redis_stream_messages(10, "logs:raw")
        _, messages = stream_messages[0]

        # Convert to proper format
        formatted_messages = []
        for msg_id, fields in messages:
            fields_bytes = {
                k.encode(): v.encode() if isinstance(v, str) else v
                for k, v in fields.items()
            }
            formatted_messages.append((msg_id, fields_bytes))

        with patch("elasticsearch.helpers.bulk", return_value=(10, [])):
            consumer._process_message_batch(formatted_messages)

        # Verify acknowledgment
        mock_redis.xack.assert_called_once()

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.config")
    def test_process_pending_messages(self, mock_config, mock_redis, pending_messages):
        """Test processing messages that failed in other consumers"""
        from apps.log_worker.app import RedisStreamsConsumer

        mock_config.elasticsearch_index_prefix = "test"

        # Setup pending messages
        pending = pending_messages(5, idle_time=70000)
        mock_redis.xpending_range.return_value = pending

        # Setup claimed messages
        claimed_msgs = [(p["message_id"], {"message": "test"}) for p in pending]
        mock_redis.xclaim.return_value = claimed_msgs

        consumer = RedisStreamsConsumer("logs:raw", "test-group", "test-consumer")

        with patch("elasticsearch.helpers.bulk", return_value=(5, [])):
            consumer._process_pending_messages()

        # Verify claim and processing
        mock_redis.xclaim.assert_called_once()
        mock_redis.xack.assert_called()

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.config")
    def test_update_queue_metrics(self, mock_config, mock_redis):
        """Test queue lag metrics update"""
        from apps.log_worker.app import RedisStreamsConsumer

        mock_config.elasticsearch_index_prefix = "test"

        mock_redis.xinfo_stream.return_value = {"length": 42}
        mock_redis.xinfo_groups.return_value = [
            {"name": "test-group", "last-delivered-id": "1234567890-0"}
        ]

        consumer = RedisStreamsConsumer("logs:raw", "test-group", "test-consumer")
        consumer._update_queue_metrics()

        # Verify stream info was queried
        mock_redis.xinfo_stream.assert_called_with("logs:raw")


@pytest.mark.integration
class TestWorkerLifecycle:
    """Tests for worker startup, shutdown, and lifecycle"""

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.license_client")
    @patch("apps.log-worker.app.config")
    def test_signal_handler_setup(
        self, mock_config, mock_license, mock_es, mock_redis, mock_signal_handler
    ):
        """Test signal handlers for graceful shutdown"""
        import signal

        from apps.log_worker.app import setup_signal_handlers

        setup_signal_handlers()

        # Verify SIGTERM and SIGINT handlers were registered
        calls = mock_signal_handler.call_args_list
        signals_registered = [call[0][0] for call in calls]

        assert signal.SIGTERM in signals_registered
        assert signal.SIGINT in signals_registered

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.config")
    @patch("apps.log-worker.app.PROCESSOR_WORKERS", 2)
    def test_start_consumer_workers(self, mock_config, mock_redis, mock_thread_pool):
        """Test starting multiple consumer workers"""
        from apps.log_worker.app import start_consumer_workers

        mock_config.elasticsearch_index_prefix = "test"

        start_consumer_workers()

        # Verify thread pool was created
        assert mock_thread_pool.called

        # Verify workers were submitted to thread pool
        pool_instance = mock_thread_pool.return_value
        assert pool_instance.submit.call_count >= 2

    @patch("apps.log-worker.app.shutdown_requested", False)
    @patch("apps.log-worker.app.worker_pool")
    @patch("apps.log-worker.app.license_client")
    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.es_client")
    @patch("time.sleep")
    def test_graceful_shutdown(
        self, mock_sleep, mock_es, mock_redis, mock_license, mock_pool
    ):
        """Test graceful shutdown of workers"""
        from apps.log_worker import app

        mock_redis.ping.return_value = True
        mock_es.ping.return_value = True
        mock_license.validate.return_value = {"valid": True, "tier": "enterprise"}

        # Simulate shutdown after first iteration
        with patch("apps.log-worker.app.shutdown_requested", side_effect=[False, True]):
            with patch("apps.log-worker.app.start_consumer_workers"):
                try:
                    app.main()
                except SystemExit:
                    pass

        # Verify pool shutdown was called
        if mock_pool:
            mock_pool.shutdown.assert_called()


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling and resilience"""

    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.config")
    def test_elasticsearch_connection_failure(
        self, mock_config, mock_es, sample_log_batch
    ):
        """Test handling Elasticsearch connection failure"""
        from apps.log_worker.app import ElasticsearchProcessor

        mock_config.elasticsearch_index_prefix = "test"

        # Simulate connection error
        with patch(
            "elasticsearch.helpers.bulk", side_effect=Exception("Connection failed")
        ):
            processor = ElasticsearchProcessor()
            result = processor.process_logs_batch(sample_log_batch)

            # Should return 0 on error
            assert result == 0

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.config")
    def test_redis_connection_error_handling(self, mock_config, mock_redis):
        """Test handling Redis connection errors"""
        from apps.log_worker.app import RedisStreamsConsumer

        mock_config.elasticsearch_index_prefix = "test"

        mock_redis.xreadgroup.side_effect = redis.ConnectionError("Connection lost")

        consumer = RedisStreamsConsumer("logs:raw", "test-group", "test-consumer")

        # Should not raise exception
        with patch("time.sleep"):
            with patch(
                "apps.log-worker.app.shutdown_requested", side_effect=[False, True]
            ):
                consumer.consume_messages()

    @patch("apps.log-worker.app.config")
    def test_malformed_log_message_handling(self, mock_config):
        """Test handling malformed log messages"""
        from apps.log_worker.app import ElasticsearchProcessor

        mock_config.elasticsearch_index_prefix = "test"

        processor = ElasticsearchProcessor()

        # Malformed message
        malformed = [(b"msg-1", {b"invalid_field": b"value"}), (b"msg-2", None)]

        # Should not crash
        result = processor.process_logs_batch(malformed)


@pytest.mark.e2e
class TestEndToEnd:
    """End-to-end tests requiring real services"""

    @pytest.mark.skip(reason="Requires real Redis and Elasticsearch")
    def test_full_log_pipeline(self):
        """Test complete log ingestion to Elasticsearch pipeline"""
        # This would test with real Redis and Elasticsearch instances
        pass

    @pytest.mark.skip(reason="Requires real Redis")
    def test_consumer_group_coordination(self):
        """Test multiple consumers coordinating via consumer groups"""
        # This would test consumer group behavior with real Redis
        pass


@pytest.mark.integration
class TestPrometheusMetrics:
    """Tests for internal Prometheus metrics"""

    @patch("apps.log-worker.app.redis_client")
    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.config")
    def test_metrics_exposed(self, mock_config, mock_es, mock_redis):
        """Test that Prometheus metrics are properly exposed"""
        from apps.log_worker.app import (
            active_workers, logs_processed_counter, metrics_forwarded_counter,
            processing_duration, queue_lag,
        )

        # Verify metrics objects exist
        assert logs_processed_counter is not None
        assert metrics_forwarded_counter is not None
        assert processing_duration is not None
        assert queue_lag is not None
        assert active_workers is not None

    @patch("apps.log-worker.app.es_client")
    @patch("apps.log-worker.app.config")
    def test_processing_metrics_incremented(
        self, mock_config, mock_es, sample_log_batch
    ):
        """Test that processing metrics are incremented"""
        from apps.log_worker.app import ElasticsearchProcessor, logs_processed_counter

        mock_config.elasticsearch_index_prefix = "test"

        initial_value = logs_processed_counter.labels(
            destination="elasticsearch", status="success"
        )._value.get()

        with patch("elasticsearch.helpers.bulk", return_value=(10, [])):
            processor = ElasticsearchProcessor()
            processor.process_logs_batch(sample_log_batch)

        # Metric should have increased
        final_value = logs_processed_counter.labels(
            destination="elasticsearch", status="success"
        )._value.get()

        assert final_value > initial_value
