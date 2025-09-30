import os
import json
from datetime import datetime
from py4web import action, request, response, Field, DAL
from prometheus_client import Counter, generate_latest
import redis

# Basic configuration
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
    db.commit()
except Exception as table_error:
    print(f"Note: Table creation skipped - {table_error}")

print(f"✓ KillKrill Metrics Receiver initialized")

# Metrics
received_metrics_counter = Counter('killkrill_metrics_received_total', 'Total metrics received', ['metric_type'])

@action('healthz', method=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_client.ping()

        # Check database connection
        db.executesql("SELECT 1")

        return {
            'status': 'healthy',
            'service': 'killkrill-metrics',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'redis': 'ok',
                'database': 'ok'
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
    return generate_latest()

@action('api/v1/metrics', method=['POST'])
def receive_metrics():
    """Simple metrics ingestion endpoint"""
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
        db.received_metrics.insert(
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
            'metric_name': metric_name,
            'metric_type': metric_type,
            'metric_value': metric_value,
            'labels': labels,
            'timestamp': datetime.utcnow().isoformat(),
            'client_ip': client_ip
        }
        redis_client.xadd('metrics:raw', stream_data)

        # Update counter
        received_metrics_counter.labels(metric_type=metric_type).inc()

        return {
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@action('index', method=['GET'])
def index():
    """Basic status page"""
    metrics_count = db(db.received_metrics).count()
    return f"""
    <html>
    <head><title>KillKrill Metrics Receiver</title></head>
    <body>
        <h1>KillKrill Metrics Receiver</h1>
        <p>High-performance metrics collection service</p>
        <ul>
            <li><a href="/healthz">Health Check</a></li>
            <li><a href="/metrics">Metrics</a></li>
            <li><strong>Total metrics received:</strong> {metrics_count}</li>
        </ul>
        <h2>Usage</h2>
        <p>Send metrics via POST to <code>/api/v1/metrics</code></p>
        <pre>
curl -X POST http://localhost:8082/api/v1/metrics \\
  -H "Content-Type: application/json" \\
  -d '{{"name": "test_metric", "type": "gauge", "value": 42}}'
        </pre>
    </body>
    </html>
    """