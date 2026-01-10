"""Prometheus metrics endpoint."""

from prometheus_client import generate_latest
from quart import Blueprint, Response, current_app

bp = Blueprint("metrics", __name__)


@bp.route("/metrics", methods=["GET"])
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    metrics_data = generate_latest()
    return Response(metrics_data, mimetype="text/plain")
