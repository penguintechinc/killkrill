"""
KillKrill Metrics Receiver - py4web Application
High-performance metrics ingestion service with Fleet integration
"""

import os
import json
from datetime import datetime
from py4web import action, request, response, DAL, Field, HTTP
from py4web.utils.cors import CORS
from prometheus_client import Counter, generate_latest
import redis

# Application name
__version__ = "1.0.0"

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://killkrill:killkrill123@postgres:5432/killkrill')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379')

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace('postgresql://', 'postgres://')

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

# Create basic tables
try:
    db.define_table('received_metrics',
        Field('metric_name', 'string', length=255),
        Field('metric_type', 'string', length=50),
        Field('metric_value', 'double'),
        Field('labels', 'text'),  # JSON
        Field('timestamp', 'datetime', default=datetime.utcnow),
        Field('source_ip', 'string', length=45),
        migrate=True
    )

    db.define_table('fleet_metrics',
        Field('host_identifier', 'string'),
        Field('metric_name', 'string'),
        Field('metric_value', 'text'),  # Can be various types
        Field('timestamp', 'datetime', default=datetime.utcnow),
        Field('labels', 'text'),  # JSON
        migrate=True
    )

    db.commit()
except Exception as table_error:
    print(f"Note: Metrics table creation skipped - {table_error}")

print(f"✓ KillKrill Metrics Receiver py4web app initialized")

# Metrics
received_metrics_counter = Counter('killkrill_metrics_received_total', 'Total metrics received', ['metric_type'])
fleet_metrics_counter = Counter('killkrill_fleet_metrics_received_total', 'Fleet metrics received', ['host'])
health_checks = Counter('killkrill_metrics_receiver_health_checks_total', 'Health checks', ['status'])

@action('index')
@action('index.html')
def index():
    """Basic status page"""
    try:
        db = get_db()
        metrics_count = db(db.received_metrics).count()
    except:
        metrics_count = "N/A"
    return f"""
    <html>
    <head><title>KillKrill Metrics Receiver</title></head>
    <body>
        <h1>KillKrill Metrics Receiver</h1>
        <p>High-performance metrics collection service</p>
        <ul>
            <li><a href="/metricsreceiver/healthz">Health Check</a></li>
            <li><a href="/metricsreceiver/metrics">Metrics</a></li>
            <li><strong>Total metrics received:</strong> {metrics_count}</li>
        </ul>
        <h2>Usage</h2>
        <p>Send metrics via POST to <code>/metricsreceiver/api/v1/metrics</code></p>
        <pre>
curl -X POST http://localhost:8082/metricsreceiver/api/v1/metrics \\
  -H "Content-Type: application/json" \\
  -d '{{"name": "test_metric", "type": "gauge", "value": 42}}'
        </pre>
    </body>
    </html>
    """

@action('healthz')
@action.uses(CORS())
def healthz():
    """Health check endpoint"""
    try:
        # Test Redis
        redis_client.ping()

        # Test database
        db.executesql("SELECT 1")

        health_checks.labels(status='ok').inc()

        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'killkrill-metrics-receiver',
            'components': {
                'database': 'ok',
                'redis': 'ok'
            }
        }
    except Exception as e:
        health_checks.labels(status='error').inc()
        response.status = 503
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

@action('metrics')
def metrics():
    """Prometheus metrics endpoint"""
    response.headers['Content-Type'] = 'text/plain; version=0.0.4; charset=utf-8'
    return generate_latest()

@action('api/v1/metrics', method=['POST'])
@action.uses(CORS())
def ingest_metrics():
    """Standard metrics ingestion endpoint"""
    try:
        data = request.json
        if not data:
            response.status = 400
            return {'error': 'No JSON data provided'}

        # Simple processing - just store the metric
        metric_name = data.get('name', 'unknown')
        metric_type = data.get('type', 'gauge')
        metric_value = float(data.get('value', 0))
        labels = json.dumps(data.get('labels', {}))
        client_ip = request.environ.get('REMOTE_ADDR', '127.0.0.1')

        # Store in database
        metric_id = db.received_metrics.insert(
            metric_name=metric_name,
            metric_type=metric_type,
            metric_value=metric_value,
            labels=labels,
            timestamp=datetime.utcnow(),
            source_ip=client_ip
        )
        db.commit()

        # Send to Redis stream
        stream_data = {
            'id': str(metric_id),
            'metric_name': metric_name,
            'metric_type': metric_type,
            'metric_value': str(metric_value),
            'labels': labels,
            'timestamp': datetime.utcnow().isoformat(),
            'client_ip': client_ip
        }
        redis_client.xadd('metrics:raw', stream_data)

        # Update counter
        received_metrics_counter.labels(metric_type=metric_type).inc()

        return {
            'status': 'accepted',
            'metric_id': metric_id,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        response.status = 500
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

# Fleet metrics integration endpoint
@action('fleet-metrics', method=['POST'])
@action('api/v1/fleet/metrics', method=['POST'])
@action.uses(CORS())
def ingest_fleet_metrics():
    """Fleet osquery metrics ingestion endpoint"""
    try:
        data = request.json or {}

        if not data:
            response.status = 400
            return {'error': 'No JSON data provided'}

        processed_count = 0
        host_identifier = data.get('hostIdentifier', data.get('host_identifier', 'unknown'))

        # Handle both single metrics and batch metrics
        metrics_data = data.get('metrics', [data]) if 'metrics' in data else [data]

        for metric_data in metrics_data:
            try:
                # Extract metric information from Fleet data
                metric_name = metric_data.get('name', metric_data.get('metric_name', 'unknown'))
                metric_value = metric_data.get('value', metric_data.get('metric_value', '0'))

                # Parse Fleet-specific fields
                labels_data = {
                    'host_identifier': host_identifier,
                    'fleet_source': 'osquery'
                }

                # Add any additional labels from the data
                if 'labels' in metric_data:
                    labels_data.update(metric_data['labels'])

                # Store Fleet metric
                fleet_metric_id = db.fleet_metrics.insert(
                    host_identifier=host_identifier,
                    metric_name=metric_name,
                    metric_value=str(metric_value),
                    timestamp=datetime.utcnow(),
                    labels=json.dumps(labels_data)
                )

                # Also store in standard metrics table for aggregation
                db.received_metrics.insert(
                    metric_name=f"fleet_{metric_name}",
                    metric_type='gauge',
                    metric_value=float(metric_value) if str(metric_value).replace('.','').isdigit() else 0.0,
                    labels=json.dumps(labels_data),
                    timestamp=datetime.utcnow(),
                    source_ip=request.environ.get('REMOTE_ADDR', '127.0.0.1')
                )

                # Send to Redis stream for processing
                stream_data = {
                    'id': str(fleet_metric_id),
                    'host_identifier': host_identifier,
                    'metric_name': metric_name,
                    'metric_value': str(metric_value),
                    'labels': json.dumps(labels_data),
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'fleet'
                }
                redis_client.xadd('fleet-metrics', stream_data)

                processed_count += 1
                fleet_metrics_counter.labels(host=host_identifier).inc()

            except Exception as metric_error:
                print(f"Error processing Fleet metric: {metric_error}")
                continue

        db.commit()

        return {
            'status': 'accepted',
            'processed_count': processed_count,
            'host_identifier': host_identifier,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        response.status = 500
        return {
            'error': f'Fleet metrics ingestion failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }

# Make sure the database connection is properly initialized when the module loads
try:
    db.received_metrics.id  # Test table access
    print("✓ Metrics receiver database tables verified")
except Exception as e:
    print(f"⚠️ Metrics receiver database table issue: {e}")