#!/usr/bin/env python3
"""
KillKrill Metrics Receiver
Centralized metrics collection with HTTP3/QUIC and py4web API
"""

import os
import sys
import json
import asyncio
import logging
import structlog
from datetime import datetime
from typing import Dict, Any, Optional
import redis
import httpx
from py4web import action, request, response, Field, DAL
from py4web.utils.cors import CORS
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import pydantic

from netaddr import IPNetwork
import jwt

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.licensing.client import PenguinTechLicenseClient
from shared.config.settings import get_config
from shared.monitoring.metrics import setup_metrics
from shared.auth.middleware import verify_auth

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
DATABASE_URL = config.database_url
LICENSE_KEY = config.license_key
PRODUCT_NAME = config.product_name
METRICS_PORT = int(os.getenv('METRICS_PORT', 8082))

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
license_client = PenguinTechLicenseClient(LICENSE_KEY, PRODUCT_NAME)

# Database setup - Convert postgresql:// to postgres:// for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace('postgresql://', 'postgres://')
db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

# Define tables
db.define_table('metric_sources',
    Field('name', 'string', requires=lambda v: v and len(v) <= 100, unique=True),
    Field('description', 'text'),
    Field('api_key', 'string', length=64, unique=True),
    Field('allowed_ips', 'text'),  # JSON array of IPs/CIDRs
    Field('enabled', 'boolean', default=True),
    Field('created_at', 'datetime', default=datetime.utcnow),
    Field('last_seen', 'datetime'),
    Field('metrics_count', 'bigint', default=0),
)

db.define_table('received_metrics',
    Field('source_id', 'reference metric_sources'),
    Field('metric_name', 'string', length=255),
    Field('metric_type', 'string', length=50),
    Field('metric_value', 'double'),
    Field('labels', 'text'),  # JSON
    Field('timestamp', 'datetime', default=datetime.utcnow),
    Field('source_ip', 'string', length=45),
)

# Prometheus metrics
metrics_registry = CollectorRegistry()
received_metrics_counter = Counter(
    'killkrill_metrics_received_total',
    'Total metrics received',
    ['source', 'metric_type'],
    registry=metrics_registry
)
processing_time = Histogram(
    'killkrill_metrics_processing_seconds',
    'Time spent processing metrics',
    ['source'],
    registry=metrics_registry
)
active_sources = Gauge(
    'killkrill_metrics_active_sources',
    'Number of active metric sources',
    registry=metrics_registry
)

# Pydantic models for validation
class MetricData(pydantic.BaseModel):
    name: str = pydantic.Field(..., max_length=255)
    type: str = pydantic.Field(..., regex=r'^(counter|gauge|histogram|summary)$')
    value: float
    labels: Optional[Dict[str, str]] = {}
    timestamp: Optional[datetime] = None
    help: Optional[str] = ""

class MetricsBatch(pydantic.BaseModel):
    source: str = pydantic.Field(..., max_length=100)
    metrics: list[MetricData] = pydantic.Field(..., min_items=1, max_items=1000)

def verify_ip_access(source_id: int, client_ip: str) -> bool:
    """Verify client IP against allowed IPs/CIDRs for source"""
    try:
        source = db.metric_sources[source_id]
        if not source or not source.enabled:
            return False

        if not source.allowed_ips:
            return True  # No restrictions

        allowed_networks = json.loads(source.allowed_ips)
        for network_str in allowed_networks:
            try:
                network = IPNetwork(network_str)
                if client_ip in network:
                    return True
            except Exception as e:
                logger.warning("Invalid network in allowed_ips",
                             source_id=source_id, network=network_str, error=str(e))
                continue
        return False
    except Exception as e:
        logger.error("Error verifying IP access", source_id=source_id, error=str(e))
        return False

def authenticate_request() -> Optional[int]:
    """Authenticate request via API key or JWT"""
    # Try API key first
    api_key = request.headers.get('X-API-Key') or request.query.get('api_key')
    if api_key:
        source = db(db.metric_sources.api_key == api_key).select().first()
        if source and source.enabled:
            return source.id

    # Try JWT token
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        try:
            token = auth_header[7:]
            payload = jwt.decode(token, config.jwt_secret, algorithms=['HS256'])
            source_name = payload.get('source')
            if source_name:
                source = db(db.metric_sources.name == source_name).select().first()
                if source and source.enabled:
                    return source.id
        except jwt.InvalidTokenError:
            pass

    return None

@action('healthz', method=['GET'])
@CORS()
def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_client.ping()

        # Check database connection
        db.executesql("SELECT 1")

        # Check license
        license_status = license_client.validate()

        return {
            'status': 'healthy',
            'service': 'killkrill-metrics',
            'timestamp': datetime.utcnow().isoformat(),
            'version': config.version,
            'license_valid': license_status.get('valid', False),
            'components': {
                'redis': 'ok',
                'database': 'ok',
                'license': 'ok' if license_status.get('valid') else 'error'
            }
        }
    except Exception as e:
        response.status = 503
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

@action('metrics', method=['GET'])
def prometheus_metrics():
    """Prometheus metrics endpoint"""
    response.headers['Content-Type'] = 'text/plain'
    return generate_latest(metrics_registry)

@action('api/v1/metrics', method=['POST'])
@CORS()
def receive_metrics():
    """Receive metrics via HTTP3/QUIC API"""
    try:
        # Authenticate request
        source_id = authenticate_request()
        if not source_id:
            response.status = 401
            return {'error': 'Authentication required'}

        # Verify IP access
        client_ip = request.environ.get('REMOTE_ADDR', '127.0.0.1')
        if not verify_ip_access(source_id, client_ip):
            response.status = 403
            return {'error': 'IP address not allowed'}

        # Parse and validate request
        try:
            data = request.json
            batch = MetricsBatch.parse_obj(data)
        except Exception as e:
            response.status = 400
            return {'error': f'Invalid request format: {str(e)}'}

        # Process metrics
        with processing_time.labels(source=batch.source).time():
            processed_count = process_metrics_batch(source_id, batch, client_ip)

        # Update source last seen
        db(db.metric_sources.id == source_id).update(
            last_seen=datetime.utcnow(),
            metrics_count=db.metric_sources.metrics_count + processed_count
        )
        db.commit()

        return {
            'status': 'success',
            'processed': processed_count,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("Error processing metrics", error=str(e))
        response.status = 500
        return {'error': 'Internal server error'}

def process_metrics_batch(source_id: int, batch: MetricsBatch, client_ip: str) -> int:
    """Process a batch of metrics"""
    processed = 0

    for metric in batch.metrics:
        try:
            # Store in database
            db.received_metrics.insert(
                source_id=source_id,
                metric_name=metric.name,
                metric_type=metric.type,
                metric_value=metric.value,
                labels=json.dumps(metric.labels or {}),
                timestamp=metric.timestamp or datetime.utcnow(),
                source_ip=client_ip
            )

            # Send to Redis Streams for Prometheus processing
            stream_data = {
                'source_id': source_id,
                'source': batch.source,
                'metric_name': metric.name,
                'metric_type': metric.type,
                'metric_value': metric.value,
                'labels': json.dumps(metric.labels or {}),
                'timestamp': (metric.timestamp or datetime.utcnow()).isoformat(),
                'help': metric.help or "",
                'client_ip': client_ip
            }

            redis_client.xadd('metrics:raw', stream_data)

            # Update Prometheus metrics
            received_metrics_counter.labels(
                source=batch.source,
                metric_type=metric.type
            ).inc()

            processed += 1

        except Exception as e:
            logger.error("Error processing metric",
                        metric_name=metric.name, error=str(e))
            continue

    return processed

@action('api/v1/sources', method=['GET'])
@CORS()
def list_sources():
    """List metric sources (admin only)"""
    # TODO: Add admin authentication
    sources = db(db.metric_sources.enabled == True).select(
        db.metric_sources.id,
        db.metric_sources.name,
        db.metric_sources.description,
        db.metric_sources.created_at,
        db.metric_sources.last_seen,
        db.metric_sources.metrics_count
    )

    return {
        'sources': [dict(s) for s in sources],
        'total': len(sources)
    }

@action('api/v1/sources/<source_id:int>/stats', method=['GET'])
@CORS()
def source_stats(source_id: int):
    """Get statistics for a specific source"""
    source = db.metric_sources[source_id]
    if not source:
        response.status = 404
        return {'error': 'Source not found'}

    # Get recent metrics count
    from datetime import timedelta
    recent_count = db(
        (db.received_metrics.source_id == source_id) &
        (db.received_metrics.timestamp > datetime.utcnow() - timedelta(hours=24))
    ).count()

    return {
        'source': dict(source),
        'recent_24h': recent_count,
        'status': 'active' if source.last_seen and
                  (datetime.utcnow() - source.last_seen).seconds < 300 else 'inactive'
    }

# Update active sources gauge periodically
def update_active_sources():
    """Update active sources metric"""
    try:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        active_count = db(
            (db.metric_sources.enabled == True) &
            (db.metric_sources.last_seen > cutoff)
        ).count()
        active_sources.set(active_count)
    except Exception as e:
        logger.error("Error updating active sources metric", error=str(e))

# Initialize license and periodic tasks on module load
try:
    license_status = license_client.validate()
    if not license_status.get('valid'):
        logger.error("Invalid license", status=license_status)
    else:
        logger.info("KillKrill Metrics Receiver initialized",
                    port=METRICS_PORT,
                    license_tier=license_status.get('tier'))

    # Start periodic tasks
    import threading
    import time

    def periodic_tasks():
        while True:
            try:
                update_active_sources()
                time.sleep(60)  # Update every minute
            except Exception as e:
                logger.error("Error in periodic tasks", error=str(e))
                time.sleep(60)

    threading.Thread(target=periodic_tasks, daemon=True).start()

except Exception as e:
    logger.error("Initialization error", error=str(e))