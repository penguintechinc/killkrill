"""
Health check and metrics endpoints
"""

from datetime import datetime

from prometheus_client import Counter, generate_latest
from quart import Blueprint, Response, jsonify

bp = Blueprint("health", __name__)

# Metrics
health_checks = Counter(
    "killkrill_manager_health_checks_total", "Health checks", ["status"]
)


@bp.route("/healthz", methods=["GET"])
async def healthz():
    """Health check endpoint"""
    from quart import current_app

    try:
        # Test Redis
        redis_client = current_app.config["redis_client"]
        await redis_client.ping()

        # Test database
        db = current_app.config["db"]
        db.health_checks.insert(status="ok", component="manager")
        db.commit()

        health_checks.labels(status="ok").inc()

        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "killkrill-manager",
                "components": {"database": "ok", "redis": "ok"},
            }
        )
    except Exception as e:
        health_checks.labels(status="error").inc()
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


@bp.route("/metrics", methods=["GET"])
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        generate_latest(), mimetype="text/plain; version=0.0.4; charset=utf-8"
    )
