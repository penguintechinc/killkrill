"""Health check endpoint."""

from datetime import datetime

import structlog
from quart import Blueprint, current_app, jsonify

logger = structlog.get_logger(__name__)
bp = Blueprint("health", __name__)


@bp.route("/healthz", methods=["GET"])
async def health_check():
    """Health check endpoint."""
    try:
        components = {}

        # Check Redis connection
        try:
            await current_app.redis_client.ping()
            components["redis"] = "ok"
        except Exception as e:
            components["redis"] = f"error: {str(e)}"

        # Check database connection
        try:
            current_app.db.executesql("SELECT 1")
            components["database"] = "ok"
        except Exception as e:
            components["database"] = f"error: {str(e)}"

        # Check receiver client
        if current_app.receiver_client:
            try:
                is_healthy = await current_app.receiver_client.health_check()
                components["receiver_client"] = "ok" if is_healthy else "degraded"
            except Exception as e:
                components["receiver_client"] = f"error: {str(e)}"

        # Overall status
        status = (
            "healthy" if all(v == "ok" for v in components.values()) else "degraded"
        )
        if any("error" in str(v) for v in components.values()):
            status = "unhealthy"

        response_data = {
            "status": status,
            "service": "killkrill-metrics-receiver",
            "timestamp": datetime.utcnow().isoformat(),
            "components": components,
        }

        status_code = 200 if status == "healthy" else 503
        return jsonify(response_data), status_code

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            503,
        )


@bp.route("/", methods=["GET"])
async def index():
    """Basic status page."""
    metrics_count = current_app.db(current_app.db.received_metrics).count()
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
