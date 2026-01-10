"""
KillKrill Log Receiver - Health Check Endpoint
"""

from datetime import datetime

import structlog
from quart import Blueprint, current_app, jsonify

logger = structlog.get_logger(__name__)

health_bp = Blueprint("health", __name__)


@health_bp.route("/healthz", methods=["GET"])
async def health_check():
    """Health check endpoint"""
    try:
        components = {}
        redis_client = current_app.redis_client
        db = current_app.db
        receiver_client = current_app.receiver_client

        # Test Redis
        try:
            redis_client.ping()
            components["redis"] = "ok"
        except Exception as e:
            components["redis"] = f"error: {str(e)}"

        # Test database
        try:
            db.executesql("SELECT 1")
            components["database"] = "ok"
        except Exception as e:
            components["database"] = f"error: {str(e)}"

        # Check receiver client
        if receiver_client:
            try:
                is_healthy = await receiver_client.health_check()
                components["receiver_client"] = "ok" if is_healthy else "degraded"
            except Exception as e:
                components["receiver_client"] = f"error: {str(e)}"

        # Overall status
        status = (
            "healthy" if all(v == "ok" for v in components.values()) else "degraded"
        )
        if any("error" in str(v) for v in components.values()):
            status = "unhealthy"

        status_code = 200 if status == "healthy" else 503

        return (
            jsonify(
                {
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    "service": "killkrill-log-receiver",
                    "components": components,
                }
            ),
            status_code,
        )

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
