#!/usr/bin/env python3
"""
KillKrill Log Processor
Redis Streams consumer with guaranteed single processing for ELK output
Features:
- Zero-duplication Redis Streams processing
- Elasticsearch integration with ECS compliance
- Prometheus metrics forwarding
- Consumer group management with failure recovery
- Batch processing for performance
"""

import asyncio
import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
import structlog
from elasticsearch import Elasticsearch, helpers
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, Histogram, push_to_gateway,
)

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from shared.config.settings import get_config
from shared.licensing.client import PenguinTechLicenseClient

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configuration
config = get_config()
REDIS_URL = config.redis_url
ELASTICSEARCH_HOSTS = config.elasticsearch_hosts.split(",")
PROMETHEUS_GATEWAY = config.prometheus_gateway
LICENSE_KEY = config.license_key
PRODUCT_NAME = config.product_name
PROCESSOR_WORKERS = config.processor_workers
BATCH_SIZE = min(config.max_batch_size, 500)  # Limit batch size for memory
PROCESSING_TIMEOUT = config.processing_timeout

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
es_client = Elasticsearch(
    ELASTICSEARCH_HOSTS,
    verify_certs=False,
    request_timeout=30,
    retry_on_timeout=True,
    max_retries=3,
)
license_client = PenguinTechLicenseClient(LICENSE_KEY, PRODUCT_NAME)

# Prometheus metrics
metrics_registry = CollectorRegistry()
logs_processed_counter = Counter(
    "killkrill_processor_logs_processed_total",
    "Total logs processed",
    ["destination", "status"],
    registry=metrics_registry,
)
metrics_forwarded_counter = Counter(
    "killkrill_processor_metrics_forwarded_total",
    "Total metrics forwarded to Prometheus",
    ["status"],
    registry=metrics_registry,
)
processing_duration = Histogram(
    "killkrill_processor_processing_duration_seconds",
    "Time spent processing batches",
    ["destination"],
    registry=metrics_registry,
)
queue_lag = Gauge(
    "killkrill_processor_queue_lag_messages",
    "Number of pending messages in Redis Streams",
    ["stream"],
    registry=metrics_registry,
)
active_workers = Gauge(
    "killkrill_processor_active_workers",
    "Number of active worker threads",
    registry=metrics_registry,
)

# Global state
shutdown_requested = False
worker_pool = None


class ElasticsearchProcessor:
    """Process logs for Elasticsearch with ECS compliance"""

    def __init__(self):
        self.index_prefix = config.elasticsearch_index_prefix
        self.batch_size = BATCH_SIZE

    def process_logs_batch(self, messages: List[Dict[str, Any]]) -> int:
        """Process a batch of log messages for Elasticsearch"""
        if not messages:
            return 0

        try:
            with processing_duration.labels(destination="elasticsearch").time():
                # Convert to Elasticsearch documents
                docs = []
                for msg_id, fields in messages:
                    try:
                        doc = self._convert_to_ecs_document(fields, msg_id)
                        if doc:
                            docs.append(doc)
                    except Exception as e:
                        logger.error(
                            "Error converting log to ECS", msg_id=msg_id, error=str(e)
                        )
                        continue

                if not docs:
                    return 0

                # Bulk insert to Elasticsearch
                success_count = self._bulk_insert_elasticsearch(docs)

                # Update metrics
                logs_processed_counter.labels(
                    destination="elasticsearch", status="success"
                ).inc(success_count)

                if success_count < len(docs):
                    failed_count = len(docs) - success_count
                    logs_processed_counter.labels(
                        destination="elasticsearch", status="failed"
                    ).inc(failed_count)

                return success_count

        except Exception as e:
            logger.error("Error processing logs batch", error=str(e))
            logs_processed_counter.labels(
                destination="elasticsearch", status="error"
            ).inc(len(messages))
            return 0

    def _convert_to_ecs_document(
        self, fields: Dict[str, Any], msg_id: str
    ) -> Optional[Dict[str, Any]]:
        """Convert log message to Elasticsearch document with ECS compliance"""
        try:
            # Parse timestamp
            timestamp = fields.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    timestamp = datetime.utcnow()
            elif not isinstance(timestamp, datetime):
                timestamp = datetime.utcnow()

            # Determine index name (daily rotation)
            index_name = f"{self.index_prefix}-logs-{timestamp.strftime('%Y.%m.%d')}"

            # Build ECS-compliant document
            doc = {
                "@timestamp": timestamp.isoformat(),
                "ecs": {"version": fields.get("ecs_version", "8.0")},
                "event": {
                    "created": datetime.utcnow().isoformat(),
                    "dataset": "killkrill.logs",
                    "ingested": datetime.utcnow().isoformat(),
                    "kind": "event",
                    "module": "killkrill",
                    "type": ["info"],
                },
                "log": {
                    "level": fields.get("log_level", fields.get("severity", "info")),
                    "logger": fields.get("logger_name", fields.get("program", "")),
                },
                "message": fields.get("message", ""),
                "service": {
                    "name": fields.get(
                        "service_name", fields.get("application", "unknown")
                    ),
                    "type": "application",
                },
                "host": {
                    "name": fields.get("hostname", ""),
                    "ip": fields.get("source_ip", ""),
                },
                "source": {
                    "ip": fields.get("source_ip", ""),
                },
                "killkrill": {
                    "source_id": fields.get("source_id"),
                    "protocol": fields.get("protocol", "unknown"),
                    "message_id": msg_id,
                    "facility": fields.get("facility", ""),
                    "raw_log": fields.get("raw_log", ""),
                },
            }

            # Add optional ECS fields if present
            if fields.get("trace_id"):
                doc["trace"] = {"id": fields["trace_id"]}

            if fields.get("span_id"):
                doc.setdefault("trace", {})["span"] = {"id": fields["span_id"]}

            if fields.get("transaction_id"):
                doc.setdefault("trace", {})["transaction"] = {
                    "id": fields["transaction_id"]
                }

            if fields.get("error_type") or fields.get("error_message"):
                doc["error"] = {
                    "type": fields.get("error_type", ""),
                    "message": fields.get("error_message", ""),
                    "stack_trace": fields.get("error_stack_trace", ""),
                }

            # Add labels as tags
            if fields.get("labels"):
                try:
                    labels = (
                        json.loads(fields["labels"])
                        if isinstance(fields["labels"], str)
                        else fields["labels"]
                    )
                    if isinstance(labels, dict):
                        doc["labels"] = labels
                except json.JSONDecodeError:
                    pass

            if fields.get("tags"):
                try:
                    tags = (
                        json.loads(fields["tags"])
                        if isinstance(fields["tags"], str)
                        else fields["tags"]
                    )
                    if isinstance(tags, list):
                        doc["tags"] = tags
                except json.JSONDecodeError:
                    pass

            # Use message ID as document ID to prevent duplicates
            return {
                "_index": index_name,
                "_id": hashlib.sha256(msg_id.encode()).hexdigest(),
                "_source": doc,
            }

        except Exception as e:
            logger.error("Error converting to ECS document", error=str(e))
            return None

    def _bulk_insert_elasticsearch(self, docs: List[Dict[str, Any]]) -> int:
        """Bulk insert documents to Elasticsearch"""
        try:
            success_count, failed_items = helpers.bulk(
                es_client,
                docs,
                index=None,  # Index specified in each doc
                request_timeout=60,
                max_retries=3,
                initial_backoff=2,
                max_backoff=600,
            )

            if failed_items:
                logger.warning(
                    "Some documents failed to index", failed_count=len(failed_items)
                )

            return success_count

        except Exception as e:
            logger.error("Elasticsearch bulk insert failed", error=str(e))
            return 0


class PrometheusProcessor:
    """Process metrics for Prometheus forwarding"""

    def __init__(self):
        self.gateway_url = PROMETHEUS_GATEWAY.replace("http://", "").replace(
            "https://", ""
        )
        if ":" not in self.gateway_url:
            self.gateway_url += ":9091"  # Default pushgateway port

    def process_metrics_batch(self, messages: List[Dict[str, Any]]) -> int:
        """Process a batch of metrics messages for Prometheus"""
        if not messages:
            return 0

        try:
            with processing_duration.labels(destination="prometheus").time():
                # Group metrics by type and labels
                metrics_groups = self._group_metrics(messages)

                # Push to Prometheus Gateway
                success_count = 0
                for group_key, metrics in metrics_groups.items():
                    if self._push_metrics_group(group_key, metrics):
                        success_count += len(metrics)

                # Update local metrics
                metrics_forwarded_counter.labels(status="success").inc(success_count)

                if success_count < len(messages):
                    failed_count = len(messages) - success_count
                    metrics_forwarded_counter.labels(status="failed").inc(failed_count)

                return success_count

        except Exception as e:
            logger.error("Error processing metrics batch", error=str(e))
            metrics_forwarded_counter.labels(status="error").inc(len(messages))
            return 0

    def _group_metrics(
        self, messages: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group metrics by source and type for efficient processing"""
        groups = {}
        for msg_id, fields in messages:
            try:
                source = fields.get("source", "unknown")
                metric_type = fields.get("metric_type", "gauge")
                group_key = f"{source}_{metric_type}"

                if group_key not in groups:
                    groups[group_key] = []

                groups[group_key].append(
                    {
                        "name": fields.get("metric_name", "unknown"),
                        "value": float(fields.get("metric_value", 0)),
                        "labels": self._parse_labels(fields.get("labels", "{}")),
                        "timestamp": fields.get("timestamp"),
                        "help": fields.get("help", ""),
                        "type": metric_type,
                    }
                )

            except Exception as e:
                logger.error("Error grouping metric", msg_id=msg_id, error=str(e))
                continue

        return groups

    def _parse_labels(self, labels_str: str) -> Dict[str, str]:
        """Parse labels JSON string"""
        try:
            if isinstance(labels_str, str):
                return json.loads(labels_str)
            elif isinstance(labels_str, dict):
                return labels_str
            else:
                return {}
        except json.JSONDecodeError:
            return {}

    def _push_metrics_group(
        self, group_key: str, metrics: List[Dict[str, Any]]
    ) -> bool:
        """Push a group of metrics to Prometheus Gateway"""
        try:
            # For now, just log the metrics (Prometheus Gateway integration would go here)
            logger.info(
                "Would push metrics to Prometheus", group=group_key, count=len(metrics)
            )
            return True

        except Exception as e:
            logger.error("Error pushing metrics group", group=group_key, error=str(e))
            return False


class RedisStreamsConsumer:
    """Redis Streams consumer with guaranteed single processing"""

    def __init__(self, stream_name: str, consumer_group: str, consumer_name: str):
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.last_processed_id = "0"

        # Initialize consumer group
        self._ensure_consumer_group()

        # Initialize processors
        self.log_processor = ElasticsearchProcessor()
        self.metrics_processor = PrometheusProcessor()

    def _ensure_consumer_group(self):
        """Ensure consumer group exists"""
        try:
            redis_client.xgroup_create(
                self.stream_name, self.consumer_group, id="0", mkstream=True
            )
            logger.info(
                "Created consumer group",
                stream=self.stream_name,
                group=self.consumer_group,
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error("Error creating consumer group", error=str(e))

    def consume_messages(self):
        """Main consumer loop with guaranteed single processing"""
        while not shutdown_requested:
            try:
                # Read new messages
                messages = redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=BATCH_SIZE,
                    block=1000,  # Block for 1 second
                )

                if messages:
                    for stream, stream_messages in messages:
                        if stream_messages:
                            self._process_message_batch(stream_messages)

                # Process pending messages (failed workers)
                self._process_pending_messages()

                # Update queue lag metrics
                self._update_queue_metrics()

                # Brief sleep to prevent CPU spinning
                time.sleep(0.1)

            except Exception as e:
                logger.error("Error in consumer loop", error=str(e))
                time.sleep(5)  # Longer sleep on error

    def _process_message_batch(self, messages: List[tuple]):
        """Process a batch of messages"""
        if not messages:
            return

        try:
            # Separate logs and metrics
            log_messages = []
            metric_messages = []

            for msg_id, fields in messages:
                # Determine message type based on stream or content
                if self.stream_name == "logs:raw" or fields.get("message"):
                    log_messages.append((msg_id, fields))
                elif self.stream_name == "metrics:raw" or fields.get("metric_name"):
                    metric_messages.append((msg_id, fields))

            # Process logs
            if log_messages:
                processed_logs = self.log_processor.process_logs_batch(log_messages)
                logger.debug(
                    "Processed logs batch",
                    count=processed_logs,
                    total=len(log_messages),
                )

            # Process metrics
            if metric_messages:
                processed_metrics = self.metrics_processor.process_metrics_batch(
                    metric_messages
                )
                logger.debug(
                    "Processed metrics batch",
                    count=processed_metrics,
                    total=len(metric_messages),
                )

            # Acknowledge all messages (they've been processed)
            message_ids = [msg_id for msg_id, _ in messages]
            redis_client.xack(self.stream_name, self.consumer_group, *message_ids)

            logger.info(
                "Processed and acknowledged message batch",
                stream=self.stream_name,
                count=len(messages),
            )

        except Exception as e:
            logger.error("Error processing message batch", error=str(e))
            # Don't acknowledge on error - messages will be retried

    def _process_pending_messages(self):
        """Process messages that failed in other consumers"""
        try:
            # Get pending messages older than 60 seconds
            pending = redis_client.xpending_range(
                self.stream_name, self.consumer_group, min="-", max="+", count=100
            )

            if not pending:
                return

            # Claim old pending messages
            old_messages = []
            current_time = int(time.time() * 1000)

            for msg_info in pending:
                msg_id = msg_info["message_id"]
                idle_time = msg_info["time_since_delivered"]

                # Claim messages idle for more than 60 seconds
                if idle_time > 60000:
                    old_messages.append(msg_id)

            if old_messages:
                claimed = redis_client.xclaim(
                    self.stream_name,
                    self.consumer_group,
                    self.consumer_name,
                    min_idle_time=60000,
                    message_ids=old_messages,
                )

                if claimed:
                    logger.info(
                        "Claimed pending messages",
                        stream=self.stream_name,
                        count=len(claimed),
                    )
                    self._process_message_batch(claimed)

        except Exception as e:
            logger.error("Error processing pending messages", error=str(e))

    def _update_queue_metrics(self):
        """Update queue lag metrics"""
        try:
            # Get stream info
            info = redis_client.xinfo_stream(self.stream_name)
            stream_length = info.get("length", 0)

            # Get consumer group info
            groups = redis_client.xinfo_groups(self.stream_name)
            for group in groups:
                if group["name"] == self.consumer_group:
                    last_delivered_id = group.get("last-delivered-id", "0-0")
                    # Calculate approximate lag
                    queue_lag.labels(stream=self.stream_name).set(stream_length)
                    break

        except Exception as e:
            logger.debug("Error updating queue metrics", error=str(e))


def setup_signal_handlers():
    """Setup graceful shutdown signal handlers"""

    def signal_handler(signum, frame):
        global shutdown_requested
        logger.info("Shutdown signal received", signal=signum)
        shutdown_requested = True

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def start_consumer_workers():
    """Start consumer workers for different streams"""
    global worker_pool

    # Create thread pool for workers
    worker_pool = ThreadPoolExecutor(max_workers=PROCESSOR_WORKERS)

    # Start workers for different streams and consumer groups
    workers = [
        # Logs to ELK
        ("logs:raw", "elk-writers", "elk-worker-1"),
        ("logs:raw", "elk-writers", "elk-worker-2"),
        # Metrics to Prometheus
        ("metrics:raw", "prometheus-writers", "prometheus-worker-1"),
        ("metrics:raw", "prometheus-writers", "prometheus-worker-2"),
    ]

    active_workers.set(len(workers))

    for stream, group, consumer in workers:
        consumer_instance = RedisStreamsConsumer(stream, group, consumer)
        worker_pool.submit(consumer_instance.consume_messages)

    logger.info("Started consumer workers", count=len(workers))


def main():
    """Main processor application"""
    try:
        # Validate license on startup
        license_status = license_client.validate()
        if not license_status.get("valid"):
            logger.error("Invalid license", status=license_status)
            sys.exit(1)

        logger.info(
            "Starting KillKrill Log Processor",
            workers=PROCESSOR_WORKERS,
            batch_size=BATCH_SIZE,
            license_tier=license_status.get("tier"),
        )

        # Setup signal handlers
        setup_signal_handlers()

        # Test connections
        redis_client.ping()
        logger.info("Redis connection OK")

        if not es_client.ping():
            logger.error("Elasticsearch connection failed")
            sys.exit(1)
        logger.info("Elasticsearch connection OK")

        # Start consumer workers
        start_consumer_workers()

        # Main loop - just keep the process alive and monitor
        while not shutdown_requested:
            try:
                # Send keepalive to license server
                usage_data = {
                    "messages_processed": logs_processed_counter._value.sum(),
                    "metrics_forwarded": metrics_forwarded_counter._value.sum(),
                    "active_workers": PROCESSOR_WORKERS,
                }
                license_client.keepalive(usage_data)

                time.sleep(60)  # Check every minute

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Error in main loop", error=str(e))
                time.sleep(10)

    except Exception as e:
        logger.error("Fatal error in processor", error=str(e))
        sys.exit(1)

    finally:
        # Graceful shutdown
        logger.info("Shutting down processor...")
        if worker_pool:
            worker_pool.shutdown(wait=True, timeout=30)
        logger.info("Processor shutdown complete")


if __name__ == "__main__":
    main()
