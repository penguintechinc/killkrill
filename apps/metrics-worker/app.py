#!/usr/bin/env python3
"""
KillKrill Metrics Worker
Processes metrics from Redis Streams and forwards to Prometheus, HDFS, SPARC, or GCP Bigtable
"""

import os
import sys
import json
import time
import logging
import structlog
import signal
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
import redis
import requests
import pydantic
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, push_to_gateway

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.licensing.client import PenguinTechLicenseClient
from shared.config.settings import get_config

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
        structlog.processors.JSONRenderer()
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
LICENSE_KEY = config.license_key
PRODUCT_NAME = config.product_name
PROMETHEUS_GATEWAY = config.prometheus_gateway
PROMETHEUS_PUSH_INTERVAL = config.prometheus_push_interval
PROCESSOR_WORKERS = config.processor_workers
BATCH_SIZE = config.max_batch_size

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
license_client = PenguinTechLicenseClient(LICENSE_KEY, PRODUCT_NAME)

# Processing metrics
processing_registry = CollectorRegistry()
metrics_processed_counter = Counter(
    'killkrill_metrics_processed_total',
    'Total metrics processed',
    ['source', 'destination', 'metric_type'],
    registry=processing_registry
)
processing_errors_counter = Counter(
    'killkrill_metrics_processing_errors_total',
    'Total metrics processing errors',
    ['source', 'destination', 'error_type'],
    registry=processing_registry
)
processing_time = Histogram(
    'killkrill_metrics_processing_duration_seconds',
    'Time spent processing metrics',
    ['source', 'destination'],
    registry=processing_registry
)
queue_size_gauge = Gauge(
    'killkrill_metrics_queue_size',
    'Current metrics queue size',
    ['stream'],
    registry=processing_registry
)


class MetricEntry(pydantic.BaseModel):
    """Prometheus-compatible metric entry"""
    name: str
    type: str  # counter, gauge, histogram, summary
    value: float
    labels: Optional[Dict[str, str]] = {}
    timestamp: Optional[str] = None
    help: Optional[str] = None


class PrometheusDestination:
    """Prometheus metrics destination"""

    def __init__(self, gateway_url: str, push_interval: int = 15):
        self.gateway_url = gateway_url
        self.push_interval = push_interval
        self.metrics_buffer = []
        self.buffer_lock = threading.Lock()
        self.last_push = 0

    def add_metric(self, metric_data: Dict[str, Any]) -> bool:
        """Add metric to buffer for batch processing"""
        try:
            metric = MetricEntry.parse_obj(metric_data)

            with self.buffer_lock:
                self.metrics_buffer.append({
                    'name': metric.name,
                    'type': metric.type,
                    'value': metric.value,
                    'labels': metric.labels or {},
                    'timestamp': metric.timestamp or datetime.utcnow().isoformat(),
                    'help': metric.help or f"Metric {metric.name}"
                })

                # Push if buffer is full or interval elapsed
                current_time = time.time()
                if (len(self.metrics_buffer) >= 100 or
                    current_time - self.last_push >= self.push_interval):
                    self._push_metrics()

            return True

        except Exception as e:
            logger.error("Failed to add metric to Prometheus buffer", error=str(e))
            return False

    def _push_metrics(self):
        """Push buffered metrics to Prometheus"""
        if not self.metrics_buffer:
            return

        try:
            # Group metrics by name and type
            metric_groups = {}
            for metric in self.metrics_buffer:
                key = (metric['name'], metric['type'])
                if key not in metric_groups:
                    metric_groups[key] = []
                metric_groups[key].append(metric)

            # Convert to Prometheus format
            prometheus_data = []
            for (name, metric_type), metrics in metric_groups.items():
                # Add HELP and TYPE lines
                if metrics:
                    prometheus_data.append(f"# HELP {name} {metrics[0]['help']}")
                    prometheus_data.append(f"# TYPE {name} {metric_type}")

                    for metric in metrics:
                        labels_str = ""
                        if metric['labels']:
                            label_pairs = [f'{k}="{v}"' for k, v in metric['labels'].items()]
                            labels_str = "{" + ",".join(label_pairs) + "}"

                        prometheus_data.append(f"{name}{labels_str} {metric['value']}")

            # Send to Prometheus Gateway
            payload = "\n".join(prometheus_data)
            response = requests.post(
                f"{self.gateway_url}/metrics/job/killkrill-metrics",
                data=payload,
                headers={'Content-Type': 'text/plain'},
                timeout=30
            )

            if response.status_code == 200:
                logger.info("Pushed metrics to Prometheus", count=len(self.metrics_buffer))
                self.metrics_buffer.clear()
                self.last_push = time.time()
            else:
                logger.error("Failed to push metrics to Prometheus",
                           status_code=response.status_code,
                           response=response.text)

        except Exception as e:
            logger.error("Error pushing metrics to Prometheus", error=str(e))


class HDFSDestination:
    """HDFS metrics destination for big data analytics"""

    def __init__(self, hdfs_url: str):
        self.hdfs_url = hdfs_url
        self.enabled = False
        logger.info("HDFS destination initialized (placeholder)", url=hdfs_url)

    def add_metric(self, metric_data: Dict[str, Any]) -> bool:
        """Add metric to HDFS (placeholder implementation)"""
        # TODO: Implement HDFS integration
        logger.debug("Would send metric to HDFS", metric=metric_data)
        return True


class SPARCDestination:
    """Apache Spark destination for stream processing"""

    def __init__(self, spark_url: str):
        self.spark_url = spark_url
        self.enabled = False
        logger.info("SPARC destination initialized (placeholder)", url=spark_url)

    def add_metric(self, metric_data: Dict[str, Any]) -> bool:
        """Add metric to Spark (placeholder implementation)"""
        # TODO: Implement Spark integration
        logger.debug("Would send metric to Spark", metric=metric_data)
        return True


class GCPBigtableDestination:
    """Google Cloud Bigtable destination for time-series data"""

    def __init__(self, project_id: str, instance_id: str):
        self.project_id = project_id
        self.instance_id = instance_id
        self.enabled = False
        logger.info("GCP Bigtable destination initialized (placeholder)",
                   project=project_id, instance=instance_id)

    def add_metric(self, metric_data: Dict[str, Any]) -> bool:
        """Add metric to Bigtable (placeholder implementation)"""
        # TODO: Implement Bigtable integration
        logger.debug("Would send metric to Bigtable", metric=metric_data)
        return True


class MetricsWorker:
    """Redis Streams consumer for metrics processing"""

    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.stream_name = "metrics:raw"
        self.consumer_group = "metrics-workers"
        self.consumer_name = f"worker-{worker_id}"
        self.running = False

        # Initialize destinations
        self.destinations = {
            'prometheus': PrometheusDestination(
                PROMETHEUS_GATEWAY,
                PROMETHEUS_PUSH_INTERVAL
            )
        }

        # Add additional destinations based on configuration
        if hasattr(config, 'hdfs_url') and config.hdfs_url:
            self.destinations['hdfs'] = HDFSDestination(config.hdfs_url)

        if hasattr(config, 'spark_url') and config.spark_url:
            self.destinations['spark'] = SPARCDestination(config.spark_url)

        if hasattr(config, 'gcp_project_id') and config.gcp_project_id:
            self.destinations['bigtable'] = GCPBigtableDestination(
                config.gcp_project_id,
                config.gcp_instance_id
            )

        self._create_consumer_group()

    def _create_consumer_group(self):
        """Create Redis Streams consumer group"""
        try:
            redis_client.xgroup_create(
                self.stream_name,
                self.consumer_group,
                id='0',
                mkstream=True
            )
            logger.info("Created consumer group", group=self.consumer_group)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info("Consumer group already exists", group=self.consumer_group)
            else:
                raise

    def start(self):
        """Start the metrics worker"""
        self.running = True
        logger.info("Starting metrics worker", worker_id=self.worker_id)

        while self.running:
            try:
                self.consume_messages()
            except Exception as e:
                logger.error("Error in metrics worker", worker_id=self.worker_id, error=str(e))
                time.sleep(5)  # Brief pause before retrying

    def stop(self):
        """Stop the metrics worker"""
        self.running = False
        logger.info("Stopping metrics worker", worker_id=self.worker_id)

    def consume_messages(self):
        """Consume and process messages from Redis Streams"""
        try:
            # Read messages from stream
            messages = redis_client.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_name: ">"},
                count=BATCH_SIZE,
                block=1000  # 1 second timeout
            )

            if not messages:
                # Update queue size metric
                stream_info = redis_client.xinfo_stream(self.stream_name)
                queue_size_gauge.labels(stream=self.stream_name).set(stream_info.get('length', 0))
                return

            # Process messages
            for stream, msgs in messages:
                if msgs:
                    self.process_message_batch(stream.decode(), msgs)

        except redis.exceptions.ConnectionError as e:
            logger.error("Redis connection error", error=str(e))
            time.sleep(5)
        except Exception as e:
            logger.error("Error consuming messages", error=str(e))

    def process_message_batch(self, stream: str, messages: List[tuple]):
        """Process a batch of messages"""
        message_ids = []
        processed_count = 0

        for message_id, fields in messages:
            try:
                with processing_time.labels(
                    source=fields.get(b'source', b'unknown').decode(),
                    destination='all'
                ).time():

                    # Decode message fields
                    metric_data = {
                        k.decode(): v.decode() if isinstance(v, bytes) else v
                        for k, v in fields.items()
                    }

                    # Process metric
                    if self.process_metric(metric_data):
                        processed_count += 1

                    message_ids.append(message_id)

            except Exception as e:
                logger.error("Error processing metric message",
                           message_id=message_id.decode(),
                           error=str(e))
                # Still acknowledge to prevent infinite retries
                message_ids.append(message_id)

        # Acknowledge processed messages
        if message_ids:
            try:
                redis_client.xack(self.stream_name, self.consumer_group, *message_ids)
                logger.debug("Acknowledged messages",
                           count=len(message_ids),
                           processed=processed_count)
            except Exception as e:
                logger.error("Error acknowledging messages", error=str(e))

    def process_metric(self, metric_data: Dict[str, Any]) -> bool:
        """Process a single metric and send to destinations"""
        try:
            source = metric_data.get('source', 'unknown')

            # Send to all configured destinations
            success_count = 0
            for dest_name, destination in self.destinations.items():
                try:
                    if destination.add_metric(metric_data):
                        success_count += 1
                        metrics_processed_counter.labels(
                            source=source,
                            destination=dest_name,
                            metric_type=metric_data.get('type', 'unknown')
                        ).inc()
                    else:
                        processing_errors_counter.labels(
                            source=source,
                            destination=dest_name,
                            error_type='destination_error'
                        ).inc()
                except Exception as e:
                    logger.error("Error sending to destination",
                               destination=dest_name,
                               error=str(e))
                    processing_errors_counter.labels(
                        source=source,
                        destination=dest_name,
                        error_type='destination_exception'
                    ).inc()

            return success_count > 0

        except Exception as e:
            logger.error("Error processing metric", error=str(e))
            processing_errors_counter.labels(
                source=metric_data.get('source', 'unknown'),
                destination='all',
                error_type='processing_error'
            ).inc()
            return False


class MetricsProcessor:
    """Main metrics processor with multiple workers"""

    def __init__(self, num_workers: int = PROCESSOR_WORKERS):
        self.num_workers = num_workers
        self.workers = []
        self.shutdown_event = threading.Event()

    def start(self):
        """Start all worker threads"""
        logger.info("Starting metrics processor", workers=self.num_workers)

        # Start worker threads
        for i in range(self.num_workers):
            worker = MetricsWorker(i)
            thread = threading.Thread(
                target=worker.start,
                name=f"metrics-worker-{i}",
                daemon=True
            )
            thread.start()
            self.workers.append((worker, thread))

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Keep main thread alive
        self.shutdown_event.wait()

    def stop(self):
        """Stop all workers"""
        logger.info("Stopping metrics processor")

        for worker, thread in self.workers:
            worker.stop()

        # Wait for threads to finish
        for worker, thread in self.workers:
            thread.join(timeout=10)

        logger.info("Metrics processor stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal", signal=signum)
        self.shutdown_event.set()
        self.stop()


def main():
    """Main entry point"""
    # Validate license
    license_status = license_client.validate()
    if not license_status.get('valid'):
        logger.error("Invalid license", status=license_status)
        sys.exit(1)

    logger.info("Starting KillKrill Metrics Worker",
                workers=PROCESSOR_WORKERS,
                license_tier=license_status.get('tier'))

    # Start processor
    processor = MetricsProcessor()
    try:
        processor.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        processor.stop()


if __name__ == '__main__':
    main()