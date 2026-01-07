"""
KillKrill Configuration Management
Enterprise-grade configuration for centralized observability platform
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from decouple import config


@dataclass
class KillKrillConfig:
    """Main configuration class for KillKrill observability platform"""

    # Core service configuration
    database_url: str
    redis_url: str

    # License server integration
    license_key: str
    product_name: str
    license_server_url: str

    # Security settings
    jwt_secret: str
    api_key_length: int

    # Service ports
    manager_port: int
    receiver_port: int
    metrics_port: int
    processor_workers: int

    # Network settings
    syslog_port_start: int
    syslog_port_end: int
    max_sources_per_app: int

    # Processing limits
    max_batch_size: int
    max_queue_size: int
    processing_timeout: int

    # Storage retention
    metrics_retention_days: int
    logs_retention_days: int

    # Elasticsearch settings
    elasticsearch_hosts: str
    elasticsearch_index_prefix: str

    # Prometheus settings
    prometheus_gateway: str
    prometheus_push_interval: int

    # Performance settings
    redis_max_connections: int
    db_pool_size: int

    # Monitoring
    enable_detailed_metrics: bool
    log_level: str

    # Version info
    version: str

    @classmethod
    def from_env(cls) -> "KillKrillConfig":
        """Load configuration from environment variables"""

        # Read version from file
        version = "development"
        try:
            with open(
                os.path.join(os.path.dirname(__file__), "../../.version"), "r"
            ) as f:
                version = f.read().strip()
        except FileNotFoundError:
            pass

        return cls(
            # Core service configuration
            database_url=config(
                "DATABASE_URL",
                default="postgresql://killkrill:killkrill123@postgres:5432/killkrill",
            ),
            redis_url=config("REDIS_URL", default="redis://:killkrill123@redis:6379"),
            # License server integration
            license_key=config("LICENSE_KEY", default=""),
            product_name=config("PRODUCT_NAME", default="killkrill"),
            license_server_url=config(
                "LICENSE_SERVER_URL", default="https://license.penguintech.io"
            ),
            # Security settings
            jwt_secret=config(
                "JWT_SECRET", default="killkrill-secret-change-in-production"
            ),
            api_key_length=config("API_KEY_LENGTH", default=64, cast=int),
            # Service ports
            manager_port=config("MANAGER_PORT", default=8080, cast=int),
            receiver_port=config("RECEIVER_HTTP_PORT", default=8081, cast=int),
            metrics_port=config("METRICS_PORT", default=8082, cast=int),
            processor_workers=config("PROCESSOR_WORKERS", default=4, cast=int),
            # Network settings
            syslog_port_start=config(
                "RECEIVER_SYSLOG_PORT_START", default=10000, cast=int
            ),
            syslog_port_end=config("RECEIVER_SYSLOG_PORT_END", default=11000, cast=int),
            max_sources_per_app=config("MAX_SOURCES_PER_APP", default=100, cast=int),
            # Processing limits
            max_batch_size=config("MAX_BATCH_SIZE", default=1000, cast=int),
            max_queue_size=config("MAX_QUEUE_SIZE", default=100000, cast=int),
            processing_timeout=config("PROCESSING_TIMEOUT", default=30, cast=int),
            # Storage retention
            metrics_retention_days=config(
                "METRICS_RETENTION_DAYS", default=90, cast=int
            ),
            logs_retention_days=config("LOGS_RETENTION_DAYS", default=30, cast=int),
            # Elasticsearch settings
            elasticsearch_hosts=config(
                "ELASTICSEARCH_HOSTS", default="http://elasticsearch:9200"
            ),
            elasticsearch_index_prefix=config(
                "ELASTICSEARCH_INDEX_PREFIX", default="killkrill"
            ),
            # Prometheus settings
            prometheus_gateway=config(
                "PROMETHEUS_GATEWAY", default="http://prometheus:9090"
            ),
            prometheus_push_interval=config(
                "PROMETHEUS_PUSH_INTERVAL", default=15, cast=int
            ),
            # Performance settings
            redis_max_connections=config(
                "REDIS_MAX_CONNECTIONS", default=100, cast=int
            ),
            db_pool_size=config("DB_POOL_SIZE", default=20, cast=int),
            # Monitoring
            enable_detailed_metrics=config(
                "ENABLE_DETAILED_METRICS", default=True, cast=bool
            ),
            log_level=config("LOG_LEVEL", default="INFO"),
            # Version info
            version=version,
        )


# Global configuration instance
_config: Optional[KillKrillConfig] = None


def get_config() -> KillKrillConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = KillKrillConfig.from_env()
    return _config


def reload_config() -> KillKrillConfig:
    """Reload configuration from environment"""
    global _config
    _config = KillKrillConfig.from_env()
    return _config
