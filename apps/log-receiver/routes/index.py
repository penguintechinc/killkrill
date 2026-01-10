"""
KillKrill Log Receiver - Index/Status Page
"""

from quart import Blueprint, current_app

index_bp = Blueprint("index", __name__)


@index_bp.route("/", methods=["GET"])
async def index():
    """Basic status page"""
    db = current_app.db
    log_count = db(db.logs).count()

    html = f"""
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
    return html
