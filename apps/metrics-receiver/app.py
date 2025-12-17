import os
import json
import asyncio
from datetime import datetime
from py4web import action, request, response, Field, DAL
from prometheus_client import Counter, generate_latest
import redis
import structlog

# Import shared ReceiverClient
from shared.receiver_client import ReceiverClient

logger = structlog.get_logger(__name__)

# Basic configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://killkrill:killkrill123@postgres:5432/killkrill')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379')
API_URL = os.environ.get('API_URL', 'http://flask-backend:5000')
GRPC_URL = os.environ.get('GRPC_URL', 'flask-backend:50051')
RECEIVER_CLIENT_ID = os.environ.get('RECEIVER_CLIENT_ID', '')
RECEIVER_CLIENT_SECRET = os.environ.get('RECEIVER_CLIENT_SECRET', '')

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace('postgresql://', 'postgres://')

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

# Initialize ReceiverClient
receiver_client = None
if RECEIVER_CLIENT_ID and RECEIVER_CLIENT_SECRET:
    receiver_client = ReceiverClient(
        api_url=API_URL,
        grpc_url=GRPC_URL,
        client_id=RECEIVER_CLIENT_ID,
        client_secret=RECEIVER_CLIENT_SECRET
    )

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

# Authenticate receiver client on startup
async def startup_authentication():
    global receiver_client
    if receiver_client:
        try:
            await receiver_client.authenticate()
            logger.info("receiver_client_authenticated")
        except Exception as e:
            logger.error("receiver_client_authentication_failed", error=str(e))

# Run async startup
try:
    asyncio.run(startup_authentication())
except Exception as e:
    logger.warning("async_startup_failed", error=str(e))

# Metrics
received_metrics_counter = Counter('killkrill_metrics_received_total', 'Total metrics received', ['metric_type'])

@action('healthz', method=['GET'])
async def health_check():
    """Health check endpoint"""
    try:
        components = {}

        # Check Redis connection
        try:
            redis_client.ping()
            components['redis'] = 'ok'
        except Exception as e:
            components['redis'] = f'error: {str(e)}'

        # Check database connection
        try:
            db.executesql("SELECT 1")
            components['database'] = 'ok'
        except Exception as e:
            components['database'] = f'error: {str(e)}'

        # Check receiver client
        if receiver_client:
            try:
                is_healthy = await receiver_client.health_check()
                components['receiver_client'] = 'ok' if is_healthy else 'degraded'
            except Exception as e:
                components['receiver_client'] = f'error: {str(e)}'

        # Overall status
        status = 'healthy' if all(v == 'ok' for v in components.values()) else 'degraded'
        if any('error' in str(v) for v in components.values()):
            status = 'unhealthy'

        return {
            'status': status,
            'service': 'killkrill-metrics-receiver',
            'timestamp': datetime.utcnow().isoformat(),
            'components': components
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
async def receive_metrics():
    """Metrics ingestion endpoint with gRPC/REST fallback submission"""
    try:
        data = request.json
        if not data:
            response.status = 400
            return {'error': 'No JSON data provided'}

        # Process metric
        metric_name = data.get('name', 'unknown')
        metric_type = data.get('type', 'gauge')
        metric_value = float(data.get('value', 0))
        labels = json.dumps(data.get('labels', {}))
        client_ip = request.environ.get('REMOTE_ADDR', '127.0.0.1')
        timestamp = datetime.utcnow()

        # Store in database
        db.received_metrics.insert(
            metric_name=metric_name,
            metric_type=metric_type,
            metric_value=metric_value,
            labels=labels,
            timestamp=timestamp,
            source_ip=client_ip
        )
        db.commit()

        # Send to Redis stream
        stream_data = {
            'metric_name': metric_name,
            'metric_type': metric_type,
            'metric_value': str(metric_value),
            'labels': labels,
            'timestamp': timestamp.isoformat(),
            'client_ip': client_ip
        }
        redis_client.xadd('metrics:raw', stream_data)

        # Submit via ReceiverClient with retry logic
        if receiver_client:
            try:
                metric_entry = {
                    'name': metric_name,
                    'type': metric_type,
                    'value': metric_value,
                    'labels': json.loads(labels),
                    'timestamp': timestamp.isoformat(),
                    'source': client_ip
                }
                await receiver_client.submit_metrics([metric_entry])
                logger.info("metric_submitted", metric_name=metric_name)
            except Exception as e:
                logger.error("metric_submission_failed", error=str(e), metric_name=metric_name)
                # Don't fail the request - metric is already stored locally

        # Update counter
        received_metrics_counter.labels(metric_type=metric_type).inc()

        return {
            'status': 'success',
            'timestamp': timestamp.isoformat()
        }

    except Exception as e:
        logger.error("metrics_ingestion_error", error=str(e))
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