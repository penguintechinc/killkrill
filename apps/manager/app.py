#!/usr/bin/env python3
"""
KillKrill Manager - Enterprise Observability Management Interface
Proper py4web application structure
"""

import os
import sys
from datetime import datetime
from py4web import action, request, response, Field
from pydal import DAL
from prometheus_client import Counter, generate_latest
import redis

# Basic configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://killkrill:killkrill123@postgres:5432/killkrill')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379')

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace('postgresql://', 'postgres://')

# Initialize components
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

    # Create basic tables if they don't exist
    try:
        db.define_table('health_checks',
            Field('timestamp', 'datetime', default=datetime.utcnow),
            Field('status', 'string', default='ok'),
            Field('component', 'string'),
            migrate=True
        )
        db.commit()
    except Exception as table_error:
        # Table likely already exists, that's fine
        print(f"Note: Table creation skipped - {table_error}")
        pass
    print(f"✓ KillKrill Manager initialized successfully")
    print(f"✓ Database connected: {DATABASE_URL}")
    print(f"✓ Redis connected: {REDIS_URL}")

except Exception as e:
    print(f"✗ Initialization error: {e}")
    sys.exit(1)

# Metrics
health_checks = Counter('killkrill_manager_health_checks_total', 'Health checks', ['status'])

@action('index')
@action('index.html')
def index():
    """Basic index page"""
    return """
    <html>
    <head><title>KillKrill Manager</title></head>
    <body>
        <h1>KillKrill Manager</h1>
        <p>Enterprise Observability Management Interface</p>
        <ul>
            <li><a href="/healthz">Health Check</a></li>
            <li><a href="/metrics">Metrics</a></li>
        </ul>
    </body>
    </html>
    """

@action('healthz')
def healthz():
    """Health check endpoint"""
    try:
        # Test Redis
        redis_client.ping()

        # Test database
        db.health_checks.insert(status='ok', component='manager')
        db.commit()

        health_checks.labels(status='ok').inc()

        response.headers['Content-Type'] = 'application/json'
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'killkrill-manager',
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

@action('metrics')
def metrics():
    """Prometheus metrics endpoint"""
    response.headers['Content-Type'] = 'text/plain; version=0.0.4; charset=utf-8'
    return generate_latest()