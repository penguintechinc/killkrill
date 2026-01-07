"""
KillKrill Infrastructure Blueprint

Provides endpoints for monitoring and logging infrastructure status and queries.
Proxies requests to Prometheus, Elasticsearch, Grafana, Kibana, and AlertManager.
"""

from flask import Blueprint, jsonify, request, g
import structlog
import requests
from typing import Optional, Dict, Any

logger = structlog.get_logger()

# Create infrastructure blueprint
infrastructure_bp = Blueprint("infrastructure", __name__, url_prefix="/infrastructure")

# Service endpoints (configured via environment variables)
SERVICES = {
    "prometheus": "http://prometheus:9090",
    "elasticsearch": "http://elasticsearch:9200",
    "grafana": "http://grafana:3000",
    "kibana": "http://kibana:5601",
    "alertmanager": "http://alertmanager:9093",
}


def get_service_url(service: str) -> Optional[str]:
    """Get service URL from config"""
    return SERVICES.get(service.lower())


def proxy_request(
    service: str, path: str, method: str = "GET", **kwargs
) -> Dict[str, Any]:
    """Proxy request to infrastructure service"""
    url = get_service_url(service)
    if not url:
        return {
            "error": f"Unknown service: {service}",
            "correlation_id": g.get("correlation_id"),
        }, 400

    try:
        full_url = f"{url}{path}"
        logger.info(
            "proxy_request",
            service=service,
            path=path,
            method=method,
            correlation_id=g.get("correlation_id"),
        )

        response = requests.request(method=method, url=full_url, timeout=30, **kwargs)
        response.raise_for_status()

        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        logger.error(
            "proxy_request_failed",
            service=service,
            error=str(e),
            correlation_id=g.get("correlation_id"),
        )
        return {
            "error": f"Failed to reach {service}",
            "details": str(e),
            "correlation_id": g.get("correlation_id"),
        }, 503


# Prometheus endpoints
@infrastructure_bp.route("/prometheus/status", methods=["GET"])
def prometheus_status():
    """Get Prometheus service status"""
    data, status = proxy_request("prometheus", "/-/healthy")
    return jsonify(data), status


@infrastructure_bp.route("/prometheus/query", methods=["POST"])
def prometheus_query():
    """Execute PromQL query"""
    payload = request.get_json() or {}
    query = payload.get("query")

    if not query:
        return (
            jsonify(
                {
                    "error": "query parameter required",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            400,
        )

    params = {"query": query}
    data, status = proxy_request("prometheus", "/api/v1/query", "GET", params=params)
    return jsonify(data), status


@infrastructure_bp.route("/prometheus/range-query", methods=["POST"])
def prometheus_range_query():
    """Execute PromQL range query"""
    payload = request.get_json() or {}
    query = payload.get("query")
    start = payload.get("start")
    end = payload.get("end")
    step = payload.get("step", "1m")

    if not all([query, start, end]):
        return (
            jsonify(
                {
                    "error": "query, start, and end parameters required",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            400,
        )

    params = {"query": query, "start": start, "end": end, "step": step}
    data, status = proxy_request(
        "prometheus", "/api/v1/query_range", "GET", params=params
    )
    return jsonify(data), status


@infrastructure_bp.route("/prometheus/targets", methods=["GET"])
def prometheus_targets():
    """Get Prometheus targets status"""
    data, status = proxy_request("prometheus", "/api/v1/targets")
    return jsonify(data), status


# Elasticsearch endpoints
@infrastructure_bp.route("/elasticsearch/status", methods=["GET"])
def elasticsearch_status():
    """Get Elasticsearch cluster status"""
    data, status = proxy_request("elasticsearch", "/_cluster/health")
    return jsonify(data), status


@infrastructure_bp.route("/elasticsearch/indices", methods=["GET"])
def elasticsearch_indices():
    """List Elasticsearch indices"""
    data, status = proxy_request("elasticsearch", "/_cat/indices?format=json")
    return jsonify(data), status


@infrastructure_bp.route("/elasticsearch/search", methods=["POST"])
def elasticsearch_search():
    """Search Elasticsearch"""
    payload = request.get_json() or {}
    index = payload.get("index", "*")

    if "query" not in payload:
        return (
            jsonify(
                {
                    "error": "query parameter required",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            400,
        )

    headers = {"Content-Type": "application/json"}
    data, status = proxy_request(
        "elasticsearch",
        f"/{index}/_search",
        "POST",
        json=payload.get("query"),
        headers=headers,
    )
    return jsonify(data), status


# Grafana endpoints
@infrastructure_bp.route("/grafana/status", methods=["GET"])
def grafana_status():
    """Get Grafana status"""
    data, status = proxy_request("grafana", "/api/health")
    return jsonify(data), status


@infrastructure_bp.route("/grafana/dashboards", methods=["GET"])
def grafana_dashboards():
    """List Grafana dashboards"""
    data, status = proxy_request("grafana", "/api/search?type=dash-db")
    return jsonify(data), status


@infrastructure_bp.route("/grafana/datasources", methods=["GET"])
def grafana_datasources():
    """List Grafana data sources"""
    data, status = proxy_request("grafana", "/api/datasources")
    return jsonify(data), status


# Kibana endpoints
@infrastructure_bp.route("/kibana/status", methods=["GET"])
def kibana_status():
    """Get Kibana status"""
    data, status = proxy_request("kibana", "/api/status")
    return jsonify(data), status


@infrastructure_bp.route("/kibana/index-patterns", methods=["GET"])
def kibana_index_patterns():
    """List Kibana index patterns"""
    data, status = proxy_request("kibana", "/api/saved_objects/index-pattern")
    return jsonify(data), status


# AlertManager endpoints
@infrastructure_bp.route("/alertmanager/status", methods=["GET"])
def alertmanager_status():
    """Get AlertManager status"""
    data, status = proxy_request("alertmanager", "/api/v1/status")
    return jsonify(data), status


@infrastructure_bp.route("/alertmanager/alerts", methods=["GET"])
def alertmanager_alerts():
    """List active alerts"""
    data, status = proxy_request("alertmanager", "/api/v1/alerts")
    return jsonify(data), status


@infrastructure_bp.route("/alertmanager/silences", methods=["GET"])
def alertmanager_silences():
    """List alert silences"""
    data, status = proxy_request("alertmanager", "/api/v1/silences")
    return jsonify(data), status


@infrastructure_bp.route("/alertmanager/silence", methods=["POST"])
def alertmanager_create_silence():
    """Create alert silence"""
    payload = request.get_json() or {}
    headers = {"Content-Type": "application/json"}
    data, status = proxy_request(
        "alertmanager", "/api/v1/silences", "POST", json=payload, headers=headers
    )
    return jsonify(data), status


# Health check endpoint
@infrastructure_bp.route("/health", methods=["GET"])
def infrastructure_health():
    """Check health of all infrastructure services"""
    health_status = {}

    for service in SERVICES.keys():
        try:
            if service == "prometheus":
                data, status = proxy_request(service, "/-/healthy")
            elif service == "elasticsearch":
                data, status = proxy_request(service, "/_cluster/health")
            elif service == "grafana":
                data, status = proxy_request(service, "/api/health")
            elif service == "kibana":
                data, status = proxy_request(service, "/api/status")
            elif service == "alertmanager":
                data, status = proxy_request(service, "/api/v1/status")

            health_status[service] = {
                "status": "healthy" if status == 200 else "unhealthy",
                "code": status,
            }
        except Exception as e:
            logger.error("health_check_failed", service=service, error=str(e))
            health_status[service] = {"status": "error", "error": str(e)}

    all_healthy = all(s.get("status") == "healthy" for s in health_status.values())

    return jsonify(
        {
            "status": "operational" if all_healthy else "degraded",
            "services": health_status,
            "correlation_id": g.get("correlation_id"),
        }
    ), (200 if all_healthy else 503)


__all__ = [
    "infrastructure_bp",
]
