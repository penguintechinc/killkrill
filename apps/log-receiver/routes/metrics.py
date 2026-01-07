"""
KillKrill Log Receiver - Prometheus Metrics Endpoint
"""

from prometheus_client import generate_latest
from quart import Blueprint, Response

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.route("/metrics", methods=["GET"])
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    metrics_output = generate_latest()
    return Response(metrics_output, mimetype="text/plain; version=0.0.4; charset=utf-8")
