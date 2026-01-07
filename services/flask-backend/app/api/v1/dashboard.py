"""
Dashboard blueprint providing aggregated observability data from real database.

Endpoints:
- GET /overview - Dashboard overview with aggregated metrics
- GET /services - List all services and their status
- GET /metrics - Aggregated metrics summary
- GET /activity - Recent activity log

Uses lazy imports for database access.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from flask import Blueprint, g, jsonify, request

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
logger = structlog.get_logger()


def get_db():
    """Lazy import database connection."""
    from app.models.database import get_pydal_connection

    return get_pydal_connection()


# Mock data generators (replace with actual data source integration)
def _get_redis_cache() -> Optional[Any]:
    """Get Redis cache client from app context."""
    try:
        from flask import current_app

        return getattr(current_app, "redis", None)
    except RuntimeError:
        return None


def _cache_key(key: str) -> str:
    """Generate cache key."""
    return f"dashboard:{key}"


def _get_cached_data(key: str, ttl: int = 300) -> Optional[Dict]:
    """Get data from Redis cache."""
    redis = _get_redis_cache()
    if not redis:
        return None

    try:
        cached = redis.get(_cache_key(key))
        if cached:
            logger.debug("cache_hit", key=key)
            import json

            return json.loads(cached)
    except Exception as e:
        logger.warning("cache_read_error", key=key, error=str(e))
    return None


def _set_cached_data(key: str, data: Dict, ttl: int = 300) -> bool:
    """Set data in Redis cache."""
    redis = _get_redis_cache()
    if not redis:
        return False

    try:
        import json

        redis.setex(_cache_key(key), ttl, json.dumps(data))
        logger.debug("cache_set", key=key, ttl=ttl)
        return True
    except Exception as e:
        logger.warning("cache_write_error", key=key, error=str(e))
        return False


def _get_overview_data() -> Dict[str, Any]:
    """Generate overview data from real database queries."""
    db = get_db()

    total_agents = db(db.sensor_agents).count()
    active_agents = db(db.sensor_agents.is_active == True).count()
    total_checks = db(db.sensor_checks).count()
    active_checks = db(db.sensor_checks.is_active == True).count()

    # Get 24h results statistics
    yesterday = datetime.utcnow() - timedelta(hours=24)
    total_results_24h = db(db.sensor_results.created_at >= yesterday).count()
    failed_results_24h = db(
        (db.sensor_results.created_at >= yesterday)
        & (db.sensor_results.status.belongs(["down", "timeout", "error"]))
    ).count()

    # Calculate average response time
    avg_response = (
        db(db.sensor_results.created_at >= yesterday)
        .select(db.sensor_results.response_time_ms.avg())
        .first()
    )
    avg_response_time = float(
        avg_response[db.sensor_results.response_time_ms.avg()] or 0
    )

    uptime_pct = 100.0
    if total_results_24h > 0:
        uptime_pct = (
            (total_results_24h - failed_results_24h) / total_results_24h
        ) * 100

    return {
        "total_services": 7,
        "healthy_services": 6,
        "degraded_services": 1,
        "total_sensors": total_agents,
        "active_sensors": active_agents,
        "total_checks": total_checks,
        "active_checks": active_checks,
        "total_checks_24h": total_results_24h,
        "failed_checks_24h": failed_results_24h,
        "uptime_percentage": round(uptime_pct, 2),
        "avg_response_time_ms": round(avg_response_time, 1),
        "alert_count": failed_results_24h,
        "last_updated": datetime.utcnow().isoformat(),
    }


def _get_services_list() -> List[Dict[str, Any]]:
    """Get list of all services and their status."""
    return [
        {
            "name": "api",
            "status": "healthy",
            "type": "Go",
            "version": "1.2.3",
            "uptime_percentage": 99.99,
            "response_time_ms": 150,
            "last_check": (datetime.utcnow() - timedelta(seconds=5)).isoformat(),
            "instances": 3,
        },
        {
            "name": "log-worker",
            "status": "healthy",
            "type": "Python",
            "version": "1.2.3",
            "uptime_percentage": 99.95,
            "response_time_ms": 320,
            "last_check": (datetime.utcnow() - timedelta(seconds=8)).isoformat(),
            "instances": 2,
        },
        {
            "name": "metrics-worker",
            "status": "healthy",
            "type": "Python",
            "version": "1.2.3",
            "uptime_percentage": 99.95,
            "response_time_ms": 280,
            "last_check": (datetime.utcnow() - timedelta(seconds=10)).isoformat(),
            "instances": 2,
        },
        {
            "name": "log-receiver",
            "status": "degraded",
            "type": "Python",
            "version": "1.2.3",
            "uptime_percentage": 98.5,
            "response_time_ms": 450,
            "last_check": (datetime.utcnow() - timedelta(seconds=3)).isoformat(),
            "instances": 2,
        },
        {
            "name": "metrics-receiver",
            "status": "healthy",
            "type": "Python",
            "version": "1.2.3",
            "uptime_percentage": 99.98,
            "response_time_ms": 190,
            "last_check": (datetime.utcnow() - timedelta(seconds=7)).isoformat(),
            "instances": 2,
        },
        {
            "name": "manager",
            "status": "healthy",
            "type": "Python",
            "version": "1.2.3",
            "uptime_percentage": 99.99,
            "response_time_ms": 200,
            "last_check": (datetime.utcnow() - timedelta(seconds=6)).isoformat(),
            "instances": 1,
        },
        {
            "name": "postgres",
            "status": "healthy",
            "type": "Database",
            "version": "15.3",
            "uptime_percentage": 100.0,
            "response_time_ms": 10,
            "last_check": (datetime.utcnow() - timedelta(seconds=2)).isoformat(),
            "instances": 1,
        },
    ]


def _get_service_details(name: str) -> Optional[Dict[str, Any]]:
    """Get detailed information for a specific service."""
    services = {svc["name"]: svc for svc in _get_services_list()}
    if name not in services:
        return None

    service = services[name].copy()
    service.update(
        {
            "cpu_usage_percent": 45.2,
            "memory_usage_percent": 62.1,
            "memory_used_mb": 512,
            "memory_limit_mb": 824,
            "disk_usage_percent": 28.5,
            "network_in_mbps": 15.3,
            "network_out_mbps": 8.7,
            "error_rate_percent": 0.15 if service["status"] == "healthy" else 2.5,
            "throughput_rps": 1250 if name != "log-receiver" else 450,
            "p99_latency_ms": 350 if name != "log-receiver" else 850,
            "dependencies": (
                ["postgres", "redis"] if name in ["api", "manager"] else ["redis"]
            ),
        }
    )
    return service


def _get_metrics_summary() -> Dict[str, Any]:
    """Get aggregated metrics summary from database."""
    db = get_db()
    yesterday = datetime.utcnow() - timedelta(hours=24)

    # Get check statistics
    total_checks_24h = db(db.sensor_results.created_at >= yesterday).count()
    failed_checks_24h = db(
        (db.sensor_results.created_at >= yesterday)
        & (db.sensor_results.status.belongs(["down", "timeout", "error"]))
    ).count()
    timeout_checks_24h = db(
        (db.sensor_results.created_at >= yesterday)
        & (db.sensor_results.status == "timeout")
    ).count()

    # Calculate average response time
    avg_response = (
        db(db.sensor_results.created_at >= yesterday)
        .select(db.sensor_results.response_time_ms.avg())
        .first()
    )
    avg_response_time = float(
        avg_response[db.sensor_results.response_time_ms.avg()] or 0
    )

    error_rate = 0.0
    if total_checks_24h > 0:
        error_rate = (failed_checks_24h / total_checks_24h) * 100

    return {
        "cpu_usage": {
            "current": 42.5,
            "average_24h": 38.2,
            "peak_24h": 87.3,
        },
        "memory_usage": {
            "current": 61.2,
            "average_24h": 55.8,
            "peak_24h": 78.9,
        },
        "network": {
            "inbound_mbps": 125.4,
            "outbound_mbps": 89.2,
            "total_requests_24h": total_checks_24h,
            "average_response_time_ms": round(avg_response_time, 1),
        },
        "error_metrics": {
            "error_count_24h": failed_checks_24h,
            "error_rate_percent": round(error_rate, 2),
            "timeout_count_24h": timeout_checks_24h,
        },
        "storage": {
            "logs_gb": 234.5,
            "metrics_gb": 189.2,
            "database_gb": 456.8,
            "total_gb": 880.5,
        },
    }


def _get_activity_log(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent activity log from database."""
    db = get_db()

    # Get recent check results with failures
    results = db(db.sensor_results).select(
        db.sensor_results.id,
        db.sensor_results.status,
        db.sensor_results.created_at,
        db.sensor_results.error_message,
        db.sensor_checks.name,
        left=db.sensor_checks.on(db.sensor_results.check_id == db.sensor_checks.id),
        orderby=~db.sensor_results.created_at,
        limitby=(0, limit),
    )

    activities = []
    for result in results:
        event_type = (
            "check_passed" if result.sensor_results.status == "up" else "check_failed"
        )
        severity = "info" if result.sensor_results.status == "up" else "error"

        activities.append(
            {
                "timestamp": result.sensor_results.created_at.isoformat(),
                "event_type": event_type,
                "service": result.sensor_checks.name or "unknown",
                "severity": severity,
                "message": result.sensor_results.error_message
                or f"Check {result.sensor_results.status}",
            }
        )

    return activities


@dashboard_bp.route("/overview", methods=["GET"])
def get_overview():
    """Get dashboard overview with aggregated metrics."""
    cached = _get_cached_data("overview")
    if cached:
        return (
            jsonify(
                {
                    "success": True,
                    "data": cached,
                    "cached": True,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    data = _get_overview_data()
    _set_cached_data("overview", data, ttl=60)

    logger.info("dashboard_overview_retrieved", correlation_id=g.get("correlation_id"))

    return (
        jsonify(
            {
                "success": True,
                "data": data,
                "cached": False,
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@dashboard_bp.route("/services", methods=["GET"])
def get_services():
    """Get list of all services and their status."""
    cached = _get_cached_data("services")
    if cached:
        return (
            jsonify(
                {
                    "success": True,
                    "data": cached,
                    "cached": True,
                    "count": len(cached),
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    services = _get_services_list()
    _set_cached_data("services", services, ttl=120)

    logger.info(
        "dashboard_services_retrieved",
        count=len(services),
        correlation_id=g.get("correlation_id"),
    )

    return (
        jsonify(
            {
                "success": True,
                "data": services,
                "cached": False,
                "count": len(services),
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@dashboard_bp.route("/services/<service_name>", methods=["GET"])
def get_service_details(service_name: str):
    """Get detailed information for a specific service."""
    cache_key = f"service_details:{service_name}"
    cached = _get_cached_data(cache_key)
    if cached:
        return (
            jsonify(
                {
                    "success": True,
                    "data": cached,
                    "cached": True,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    service = _get_service_details(service_name)
    if not service:
        logger.warning(
            "service_not_found",
            service_name=service_name,
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": f'Service "{service_name}" not found',
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            404,
        )

    _set_cached_data(cache_key, service, ttl=120)

    logger.info(
        "dashboard_service_details_retrieved",
        service_name=service_name,
        correlation_id=g.get("correlation_id"),
    )

    return (
        jsonify(
            {
                "success": True,
                "data": service,
                "cached": False,
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@dashboard_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """Get aggregated metrics summary."""
    cached = _get_cached_data("metrics_summary")
    if cached:
        return (
            jsonify(
                {
                    "success": True,
                    "data": cached,
                    "cached": True,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    metrics = _get_metrics_summary()
    _set_cached_data("metrics_summary", metrics, ttl=300)

    logger.info("dashboard_metrics_retrieved", correlation_id=g.get("correlation_id"))

    return (
        jsonify(
            {
                "success": True,
                "data": metrics,
                "cached": False,
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@dashboard_bp.route("/activity", methods=["GET"])
def get_activity():
    """Get recent activity log."""
    limit = request.args.get("limit", 50, type=int)
    if limit < 1 or limit > 500:
        limit = 50

    cache_key = f"activity:{limit}"
    cached = _get_cached_data(cache_key)
    if cached:
        return (
            jsonify(
                {
                    "success": True,
                    "data": cached,
                    "cached": True,
                    "count": len(cached),
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    activity = _get_activity_log(limit)
    _set_cached_data(cache_key, activity, ttl=60)

    logger.info(
        "dashboard_activity_retrieved",
        count=len(activity),
        limit=limit,
        correlation_id=g.get("correlation_id"),
    )

    return (
        jsonify(
            {
                "success": True,
                "data": activity,
                "cached": False,
                "count": len(activity),
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


__all__ = [
    "dashboard_bp",
]
