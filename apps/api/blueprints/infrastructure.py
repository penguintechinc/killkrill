"""
KillKrill API - Infrastructure Blueprint
Infrastructure monitoring and configuration endpoints
"""

from datetime import datetime

import httpx
import structlog
from quart import Blueprint, jsonify, request

from config import get_config
from middleware.auth import require_auth, require_role

logger = structlog.get_logger(__name__)

infrastructure_bp = Blueprint("infrastructure", __name__)


@infrastructure_bp.route("/overview", methods=["GET"])
@require_auth()
async def get_overview():
    """Get infrastructure overview"""
    config = get_config()

    return jsonify(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "prometheus": {"url": config.PROMETHEUS_URL, "port": 9090},
                "elasticsearch": {"url": config.ELASTICSEARCH_URL, "port": 9200},
                "kibana": {"url": config.KIBANA_URL, "port": 5601},
                "grafana": {"url": config.GRAFANA_URL, "port": 3000},
                "alertmanager": {"url": config.ALERTMANAGER_URL, "port": 9093},
                "fleet_server": {"url": config.FLEET_SERVER_URL, "port": 8084},
            },
        }
    )


# ============== Prometheus ==============


@infrastructure_bp.route("/prometheus/status", methods=["GET"])
@require_auth()
async def prometheus_status():
    """Get Prometheus status"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            # Get runtime info
            runtime = await client.get(
                f"{config.PROMETHEUS_URL}/api/v1/status/runtimeinfo", timeout=5.0
            )
            # Get build info
            build = await client.get(
                f"{config.PROMETHEUS_URL}/api/v1/status/buildinfo", timeout=5.0
            )

            return jsonify(
                {
                    "status": "healthy",
                    "runtime": (
                        runtime.json().get("data", {})
                        if runtime.status_code == 200
                        else {}
                    ),
                    "build": (
                        build.json().get("data", {}) if build.status_code == 200 else {}
                    ),
                }
            )
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@infrastructure_bp.route("/prometheus/query", methods=["POST"])
@require_auth()
async def prometheus_query():
    """Execute Prometheus query"""
    config = get_config()
    data = await request.get_json()

    if not data or not data.get("query"):
        return jsonify({"error": "Query required"}), 400

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.PROMETHEUS_URL}/api/v1/query",
                params={"query": data.get("query")},
                timeout=30.0,
            )

            return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@infrastructure_bp.route("/prometheus/targets", methods=["GET"])
@require_auth()
async def prometheus_targets():
    """Get Prometheus scrape targets"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.PROMETHEUS_URL}/api/v1/targets", timeout=10.0
            )
            return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ============== Elasticsearch ==============


@infrastructure_bp.route("/elasticsearch/cluster", methods=["GET"])
@require_auth()
async def elasticsearch_cluster():
    """Get Elasticsearch cluster health"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            health = await client.get(
                f"{config.ELASTICSEARCH_URL}/_cluster/health", timeout=10.0
            )
            stats = await client.get(
                f"{config.ELASTICSEARCH_URL}/_cluster/stats", timeout=10.0
            )

            return jsonify(
                {
                    "health": health.json() if health.status_code == 200 else {},
                    "stats": stats.json() if stats.status_code == 200 else {},
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@infrastructure_bp.route("/elasticsearch/indices", methods=["GET"])
@require_auth()
async def elasticsearch_indices():
    """Get Elasticsearch indices"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.ELASTICSEARCH_URL}/_cat/indices",
                params={"format": "json"},
                timeout=10.0,
            )
            return jsonify(
                {"indices": response.json() if response.status_code == 200 else []}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ============== Grafana ==============


@infrastructure_bp.route("/grafana/status", methods=["GET"])
@require_auth()
async def grafana_status():
    """Get Grafana status"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.GRAFANA_URL}/api/health", timeout=5.0)
            return jsonify(
                response.json() if response.status_code == 200 else {"status": "error"}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@infrastructure_bp.route("/grafana/dashboards", methods=["GET"])
@require_auth()
async def grafana_dashboards():
    """List Grafana dashboards"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.GRAFANA_URL}/api/search",
                params={"type": "dash-db"},
                timeout=10.0,
            )
            return jsonify(
                {"dashboards": response.json() if response.status_code == 200 else []}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ============== Kibana ==============


@infrastructure_bp.route("/kibana/status", methods=["GET"])
@require_auth()
async def kibana_status():
    """Get Kibana status"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.KIBANA_URL}/api/status", timeout=10.0)
            return jsonify(
                response.json() if response.status_code == 200 else {"status": "error"}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ============== AlertManager ==============


@infrastructure_bp.route("/alertmanager/status", methods=["GET"])
@require_auth()
async def alertmanager_status():
    """Get AlertManager status"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.ALERTMANAGER_URL}/api/v2/status", timeout=5.0
            )
            return jsonify(
                response.json() if response.status_code == 200 else {"status": "error"}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@infrastructure_bp.route("/alertmanager/alerts", methods=["GET"])
@require_auth()
async def alertmanager_alerts():
    """Get active alerts from AlertManager"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.ALERTMANAGER_URL}/api/v2/alerts", timeout=10.0
            )
            return jsonify(
                {"alerts": response.json() if response.status_code == 200 else []}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503
