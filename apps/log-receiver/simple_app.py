#!/usr/bin/env python3
"""
KillKrill Log Receiver - Minimal Working Version
Simple HTTP server for testing log ingestion
"""

import os
import sys
import json
import logging
from datetime import datetime
from py4web import action, request, response, DAL
from prometheus_client import Counter, generate_latest
import redis

# Basic configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://killkrill:killkrill123@postgres:5432/killkrill')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379')
RECEIVER_PORT = int(os.environ.get('RECEIVER_PORT', '8081'))

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace('postgresql://', 'postgres://')

# Initialize components
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

    # Create basic tables
    db.define_table('logs',
        db.Field('timestamp', 'datetime', default=datetime.utcnow),
        db.Field('level', 'string'),
        db.Field('message', 'text'),
        db.Field('source', 'string'),
        migrate=True
    )

    db.commit()
    print(f"✓ KillKrill Log Receiver initialized")
    print(f"✓ Database: {DATABASE_URL}")
    print(f"✓ Redis: {REDIS_URL}")

except Exception as e:
    print(f"✗ Initialization error: {e}")
    sys.exit(1)

# Metrics
logs_received = Counter('killkrill_logs_received_total', 'Total logs received', ['level'])
health_checks = Counter('killkrill_log_receiver_health_checks_total', 'Health checks', ['status'])

@action('healthz', method=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test Redis
        redis_client.ping()

        # Test database
        db.logs.insert(level='info', message='health check', source='system')
        db.commit()

        health_checks.labels(status='ok').inc()

        response.headers['Content-Type'] = 'application/json'
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'killkrill-log-receiver',
            'components': {
                'database': 'ok',
                'redis': 'ok'
            }
        }
    except Exception as e:
        health_checks.labels(status='error').inc()
        response.status = 503
        response.headers['Content-Type'] = 'application/json'
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

@action('metrics', method=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    response.headers['Content-Type'] = 'text/plain; version=0.0.4; charset=utf-8'
    return generate_latest()

@action('api/v1/logs', method=['POST'])
def ingest_logs():
    """Simple log ingestion endpoint"""
    try:
        log_data = request.json

        # Basic validation
        if not log_data:
            response.status = 400
            return {'error': 'No JSON data provided'}

        # Extract log fields
        timestamp = log_data.get('timestamp')
        if timestamp:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            timestamp = datetime.utcnow()

        level = log_data.get('log_level', log_data.get('level', 'info'))
        message = log_data.get('message', str(log_data))
        source = log_data.get('service_name', log_data.get('source', 'unknown'))

        # Store in database
        log_id = db.logs.insert(
            timestamp=timestamp,
            level=level,
            message=message,
            source=source
        )
        db.commit()

        # Send to Redis stream
        stream_data = {
            'id': str(log_id),
            'timestamp': timestamp.isoformat(),
            'level': level,
            'message': message,
            'source': source
        }
        redis_client.xadd('logs', stream_data)

        # Update metrics
        logs_received.labels(level=level).inc()

        response.headers['Content-Type'] = 'application/json'
        return {
            'status': 'accepted',
            'log_id': log_id,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        response.status = 500
        response.headers['Content-Type'] = 'application/json'
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

@action('index', method=['GET'])
def index():
    """Basic status page"""
    log_count = db(db.logs).count()
    return f"""
    <html>
    <head><title>KillKrill Log Receiver</title></head>
    <body>
        <h1>KillKrill Log Receiver</h1>
        <p>High-performance log ingestion service</p>
        <ul>
            <li><a href="/healthz">Health Check</a></li>
            <li><a href="/metrics">Metrics</a></li>
            <li><strong>Total logs received:</strong> {log_count}</li>
        </ul>
        <h2>Usage</h2>
        <p>Send logs via POST to <code>/api/v1/logs</code></p>
        <pre>
curl -X POST http://localhost:8081/api/v1/logs \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer PENG-DEMO-DEMO-DEMO-DEMO-DEMO" \\
  -d '{{"log_level": "info", "message": "Test log", "service_name": "test"}}'
        </pre>
    </body>
    </html>
    """

if __name__ == '__main__':
    print(f"Starting KillKrill Log Receiver on port {RECEIVER_PORT}")

    # Import py4web server
    from py4web.core import wsgi
    from rocket3 import Rocket

    app = wsgi()
    server = Rocket(('0.0.0.0', RECEIVER_PORT), 'wsgi', {'wsgi_app': app})

    try:
        print(f"✓ Log Receiver listening on http://0.0.0.0:{RECEIVER_PORT}")
        print(f"✓ Send logs to http://localhost:{RECEIVER_PORT}/api/v1/logs")
        server.start()
    except KeyboardInterrupt:
        print("Log Receiver shutdown requested")
        server.stop()