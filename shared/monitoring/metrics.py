"""
KillKrill Monitoring and Metrics Utilities
Centralized metrics collection and monitoring setup
"""

import logging
from typing import Any, Dict, Optional

import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

logger = structlog.get_logger()


def setup_metrics(service_name: str) -> CollectorRegistry:
    """Setup standard metrics for a KillKrill service"""
    registry = CollectorRegistry()

    # Standard service metrics
    request_counter = Counter(
        f"killkrill_{service_name}_requests_total",
        "Total requests processed",
        ["method", "endpoint", "status"],
        registry=registry,
    )

    request_duration = Histogram(
        f"killkrill_{service_name}_request_duration_seconds",
        "Request processing time",
        ["method", "endpoint"],
        registry=registry,
    )

    active_connections = Gauge(
        f"killkrill_{service_name}_active_connections",
        "Number of active connections",
        registry=registry,
    )

    error_counter = Counter(
        f"killkrill_{service_name}_errors_total",
        "Total errors encountered",
        ["error_type"],
        registry=registry,
    )

    return registry


def setup_redis_metrics(registry: CollectorRegistry) -> Dict[str, Any]:
    """Setup Redis-specific metrics"""
    redis_operations = Counter(
        "killkrill_redis_operations_total",
        "Total Redis operations",
        ["operation", "status"],
        registry=registry,
    )

    redis_connection_pool = Gauge(
        "killkrill_redis_connection_pool_size",
        "Redis connection pool size",
        registry=registry,
    )

    redis_latency = Histogram(
        "killkrill_redis_operation_duration_seconds",
        "Redis operation latency",
        ["operation"],
        registry=registry,
    )

    return {
        "operations": redis_operations,
        "pool_size": redis_connection_pool,
        "latency": redis_latency,
    }


def setup_database_metrics(registry: CollectorRegistry) -> Dict[str, Any]:
    """Setup database-specific metrics"""
    db_operations = Counter(
        "killkrill_database_operations_total",
        "Total database operations",
        ["operation", "table", "status"],
        registry=registry,
    )

    db_connection_pool = Gauge(
        "killkrill_database_connection_pool_size",
        "Database connection pool size",
        registry=registry,
    )

    db_query_duration = Histogram(
        "killkrill_database_query_duration_seconds",
        "Database query duration",
        ["operation", "table"],
        registry=registry,
    )

    return {
        "operations": db_operations,
        "pool_size": db_connection_pool,
        "query_duration": db_query_duration,
    }


class MetricsCollector:
    """Centralized metrics collector for KillKrill services"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.registry = setup_metrics(service_name)
        self.redis_metrics = setup_redis_metrics(self.registry)
        self.db_metrics = setup_database_metrics(self.registry)

    def record_request(self, method: str, endpoint: str, status: str, duration: float):
        """Record HTTP request metrics"""
        try:
            # Find request counter in registry
            for collector in self.registry._collector_to_names:
                if hasattr(collector, "_name") and "requests_total" in collector._name:
                    collector.labels(
                        method=method, endpoint=endpoint, status=status
                    ).inc()
                elif (
                    hasattr(collector, "_name")
                    and "request_duration" in collector._name
                ):
                    collector.labels(method=method, endpoint=endpoint).observe(duration)
        except Exception as e:
            logger.error("Error recording request metrics", error=str(e))

    def record_redis_operation(self, operation: str, status: str, duration: float):
        """Record Redis operation metrics"""
        try:
            self.redis_metrics["operations"].labels(
                operation=operation, status=status
            ).inc()
            self.redis_metrics["latency"].labels(operation=operation).observe(duration)
        except Exception as e:
            logger.error("Error recording Redis metrics", error=str(e))

    def record_database_operation(
        self, operation: str, table: str, status: str, duration: float
    ):
        """Record database operation metrics"""
        try:
            self.db_metrics["operations"].labels(
                operation=operation, table=table, status=status
            ).inc()
            self.db_metrics["query_duration"].labels(
                operation=operation, table=table
            ).observe(duration)
        except Exception as e:
            logger.error("Error recording database metrics", error=str(e))

    def set_active_connections(self, count: int):
        """Set active connections gauge"""
        try:
            for collector in self.registry._collector_to_names:
                if (
                    hasattr(collector, "_name")
                    and "active_connections" in collector._name
                ):
                    collector.set(count)
                    break
        except Exception as e:
            logger.error("Error setting active connections", error=str(e))

    def increment_error(self, error_type: str):
        """Increment error counter"""
        try:
            for collector in self.registry._collector_to_names:
                if hasattr(collector, "_name") and "errors_total" in collector._name:
                    collector.labels(error_type=error_type).inc()
                    break
        except Exception as e:
            logger.error("Error incrementing error counter", error=str(e))


# Global metrics collectors for each service
_metrics_collectors: Dict[str, MetricsCollector] = {}


def get_metrics_collector(service_name: str) -> MetricsCollector:
    """Get or create metrics collector for service"""
    if service_name not in _metrics_collectors:
        _metrics_collectors[service_name] = MetricsCollector(service_name)
    return _metrics_collectors[service_name]


def export_metrics(registry: CollectorRegistry) -> str:
    """Export metrics in Prometheus format"""
    from prometheus_client import generate_latest

    return generate_latest(registry).decode("utf-8")
