"""
KillKrill Log Receiver - Prometheus Metrics Endpoint
"""

from quart import Blueprint, Response
from prometheus_client import generate_latest

metrics_bp = Blueprint('metrics', __name__)


@metrics_bp.route('/metrics', methods=['GET'])
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    metrics_output = generate_latest()
    return Response(
        metrics_output,
        mimetype='text/plain; version=0.0.4; charset=utf-8'
    )
