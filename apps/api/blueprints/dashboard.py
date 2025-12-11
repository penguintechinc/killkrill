"""
KillKrill API - Dashboard Blueprint
Dashboard data and service status endpoints
"""

from datetime import datetime
from typing import Dict, Any

from quart import Blueprint, jsonify
import httpx
import structlog

from middleware.auth import require_auth
from config import get_config
from services.redis_service import cache

logger = structlog.get_logger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/overview', methods=['GET'])
@require_auth()
async def get_overview():
    """Get dashboard overview with aggregated stats"""
    config = get_config()

    overview = {
        'timestamp': datetime.utcnow().isoformat(),
        'services': await get_all_service_status(),
        'metrics_summary': await get_metrics_summary(),
        'recent_alerts': [],  # TODO: Implement alert fetching
    }

    return jsonify(overview)


@dashboard_bp.route('/services', methods=['GET'])
@require_auth()
async def get_services():
    """Get all service statuses"""
    services = await get_all_service_status()
    return jsonify({'services': services})


@dashboard_bp.route('/services/<service_name>', methods=['GET'])
@require_auth()
async def get_service(service_name: str):
    """Get specific service status"""
    services = await get_all_service_status()

    for service in services:
        if service['name'] == service_name:
            return jsonify(service)

    return jsonify({'error': 'Service not found'}), 404


@dashboard_bp.route('/metrics', methods=['GET'])
@require_auth()
async def get_metrics():
    """Get key metrics summary"""
    summary = await get_metrics_summary()
    return jsonify(summary)


@dashboard_bp.route('/activity', methods=['GET'])
@require_auth()
async def get_activity():
    """Get recent activity"""
    # TODO: Implement activity log from audit_log table
    return jsonify({
        'activities': [],
        'total': 0,
    })


async def get_all_service_status() -> list:
    """Get status of all services"""
    config = get_config()

    services = [
        {'name': 'killkrill-api', 'url': f'http://localhost:{config.PORT}/healthz', 'type': 'internal'},
        {'name': 'log-receiver', 'url': f'{config.LOG_RECEIVER_URL}/healthz', 'type': 'internal'},
        {'name': 'metrics-receiver', 'url': f'{config.METRICS_RECEIVER_URL}/healthz', 'type': 'internal'},
        {'name': 'postgresql', 'url': None, 'type': 'database'},
        {'name': 'redis', 'url': None, 'type': 'cache'},
        {'name': 'elasticsearch', 'url': f'{config.ELASTICSEARCH_URL}/_cluster/health', 'type': 'external'},
        {'name': 'prometheus', 'url': f'{config.PROMETHEUS_URL}/-/healthy', 'type': 'external'},
        {'name': 'grafana', 'url': f'{config.GRAFANA_URL}/api/health', 'type': 'external'},
        {'name': 'kibana', 'url': f'{config.KIBANA_URL}/api/status', 'type': 'external'},
        {'name': 'alertmanager', 'url': f'{config.ALERTMANAGER_URL}/-/healthy', 'type': 'external'},
        {'name': 'fleet-server', 'url': f'{config.FLEET_SERVER_URL}/healthz', 'type': 'external'},
    ]

    results = []

    for service in services:
        status = await check_service_health(service)
        results.append(status)

    return results


async def check_service_health(service: Dict[str, Any]) -> Dict[str, Any]:
    """Check health of a single service"""
    result = {
        'name': service['name'],
        'type': service['type'],
        'status': 'unknown',
        'latency': None,
        'last_check': datetime.utcnow().isoformat(),
        'details': {}
    }

    # Check cache first
    cached = await cache.get_json(f"service_status:{service['name']}")
    if cached:
        # Use cached result if less than 30 seconds old
        return cached

    if service['type'] == 'database':
        # Check database connectivity
        try:
            from models.database import get_db
            db = await get_db()
            if db:
                result['status'] = 'healthy'
            else:
                result['status'] = 'error'
        except Exception as e:
            result['status'] = 'error'
            result['details']['error'] = str(e)

    elif service['type'] == 'cache':
        # Check Redis connectivity
        try:
            from services.redis_service import get_redis
            redis = await get_redis()
            if redis:
                start = datetime.utcnow()
                await redis.ping()
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                result['status'] = 'healthy'
                result['latency'] = round(latency, 2)
            else:
                result['status'] = 'error'
        except Exception as e:
            result['status'] = 'error'
            result['details']['error'] = str(e)

    elif service['url']:
        # HTTP health check
        try:
            async with httpx.AsyncClient() as client:
                start = datetime.utcnow()
                response = await client.get(service['url'], timeout=5.0)
                latency = (datetime.utcnow() - start).total_seconds() * 1000

                result['latency'] = round(latency, 2)

                if response.status_code == 200:
                    result['status'] = 'healthy'
                elif response.status_code < 500:
                    result['status'] = 'degraded'
                else:
                    result['status'] = 'error'

                result['details']['status_code'] = response.status_code

        except httpx.TimeoutException:
            result['status'] = 'timeout'
            result['details']['error'] = 'Connection timeout'
        except Exception as e:
            result['status'] = 'error'
            result['details']['error'] = str(e)

    # Cache result for 30 seconds
    await cache.set_json(f"service_status:{service['name']}", result, ttl=30)

    return result


async def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of key metrics from Prometheus"""
    config = get_config()

    summary = {
        'timestamp': datetime.utcnow().isoformat(),
        'logs_ingested_24h': 0,
        'metrics_ingested_24h': 0,
        'active_sensors': 0,
        'active_alerts': 0,
    }

    try:
        async with httpx.AsyncClient() as client:
            # Query Prometheus for metrics
            queries = {
                'logs_ingested_24h': 'sum(increase(killkrill_logs_received_total[24h]))',
                'metrics_ingested_24h': 'sum(increase(killkrill_metrics_received_total[24h]))',
            }

            for key, query in queries.items():
                response = await client.get(
                    f'{config.PROMETHEUS_URL}/api/v1/query',
                    params={'query': query},
                    timeout=5.0
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('data', {}).get('result'):
                        value = data['data']['result'][0].get('value', [None, 0])[1]
                        summary[key] = int(float(value))

    except Exception as e:
        logger.warning("metrics_fetch_failed", error=str(e))

    return summary
