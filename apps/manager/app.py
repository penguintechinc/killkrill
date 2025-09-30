import os
from datetime import datetime
from flask import Flask, request, jsonify
from pydal import DAL, Field
from prometheus_client import Counter, generate_latest
import redis

# Basic configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://killkrill:killkrill123@postgres:5432/killkrill')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379')

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace('postgresql://', 'postgres://')

# Initialize Flask app
app = Flask(__name__)

# Initialize components
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
    print(f"Note: Table creation skipped - {table_error}")

print(f"✓ KillKrill Manager initialized")

# Metrics
health_checks = Counter('killkrill_manager_health_checks_total', 'Health checks', ['status'])

@app.route('/', methods=['GET'])
@app.route('/index.html', methods=['GET'])
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

@app.route('/healthz', methods=['GET'])
def healthz():
    """Health check endpoint"""
    try:
        # Test Redis
        redis_client.ping()

        # Test database
        db.health_checks.insert(status='ok', component='manager')
        db.commit()

        health_checks.labels(status='ok').inc()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'killkrill-manager',
            'components': {
                'database': 'ok',
                'redis': 'ok'
            }
        })
    except Exception as e:
        health_checks.labels(status='error').inc()
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    from flask import Response
    return Response(generate_latest(), mimetype='text/plain; version=0.0.4; charset=utf-8')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)