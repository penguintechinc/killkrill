"""
Proxy Endpoints for KillKrill Manager
Provides secure proxy access to all integrated services with SSO
"""

import os
import requests
from urllib.parse import urljoin
from py4web import action, request, response, redirect
from py4web.utils.cors import CORS
from typing import Optional, Dict, Any

# Service endpoint configurations
GRAFANA_URL = os.environ.get('GRAFANA_URL', 'http://grafana:3000')
KIBANA_URL = os.environ.get('KIBANA_URL', 'http://kibana:5601')
PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://prometheus:9090')
ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
ALERTMANAGER_URL = os.environ.get('ALERTMANAGER_URL', 'http://alertmanager:9093')
FLEET_URL = os.environ.get('FLEET_SERVER_URL', 'http://fleet-server:8080')

# Authentication tokens/credentials (should be configured via environment)
GRAFANA_ADMIN_TOKEN = os.environ.get('GRAFANA_ADMIN_TOKEN', '')
ELASTICSEARCH_USERNAME = os.environ.get('ELASTICSEARCH_USERNAME', '')
ELASTICSEARCH_PASSWORD = os.environ.get('ELASTICSEARCH_PASSWORD', '')

class ServiceProxy:
    """Base class for service proxying with authentication"""

    def __init__(self, base_url: str, service_name: str):
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name

    def make_request(self, path: str, method: str = 'GET', **kwargs) -> requests.Response:
        """Make authenticated request to the proxied service"""
        url = urljoin(self.base_url + '/', path.lstrip('/'))

        # Add service-specific authentication headers
        headers = kwargs.get('headers', {})
        headers = self._add_auth_headers(headers)
        kwargs['headers'] = headers

        # Set reasonable timeout
        kwargs.setdefault('timeout', 30)

        try:
            return requests.request(method, url, **kwargs)
        except requests.RequestException as e:
            # Log error and return mock response
            print(f"Proxy request failed for {self.service_name}: {e}")
            mock_response = requests.Response()
            mock_response.status_code = 503
            mock_response._content = f'Service {self.service_name} unavailable'.encode()
            return mock_response

    def _add_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Add authentication headers (override in subclasses)"""
        return headers

class GrafanaProxy(ServiceProxy):
    """Grafana service proxy with admin token authentication"""

    def _add_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        if GRAFANA_ADMIN_TOKEN:
            headers['Authorization'] = f'Bearer {GRAFANA_ADMIN_TOKEN}'
        return headers

class ElasticsearchProxy(ServiceProxy):
    """Elasticsearch service proxy with basic authentication"""

    def _add_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        if ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
            import base64
            credentials = base64.b64encode(
                f'{ELASTICSEARCH_USERNAME}:{ELASTICSEARCH_PASSWORD}'.encode()
            ).decode()
            headers['Authorization'] = f'Basic {credentials}'
        return headers

class FleetProxy(ServiceProxy):
    """Fleet service proxy with API token authentication"""

    def _add_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        fleet_token = os.environ.get('FLEET_API_TOKEN', '')
        if fleet_token:
            headers['Authorization'] = f'Bearer {fleet_token}'
        return headers

# Initialize service proxies
grafana_proxy = GrafanaProxy(GRAFANA_URL, 'grafana')
elasticsearch_proxy = ElasticsearchProxy(ELASTICSEARCH_URL, 'elasticsearch')
fleet_proxy = FleetProxy(FLEET_URL, 'fleet')
prometheus_proxy = ServiceProxy(PROMETHEUS_URL, 'prometheus')
kibana_proxy = ServiceProxy(KIBANA_URL, 'kibana')
alertmanager_proxy = ServiceProxy(ALERTMANAGER_URL, 'alertmanager')

# Grafana Proxy Endpoints
@action('grafana')
@action('grafana/<path:path>')
def grafana_proxy_handler(path=''):
    """Proxy requests to Grafana with authentication"""
    # TODO: Add proper user authentication check

    # Handle root redirect
    if not path:
        return redirect(f'/manager/grafana/')

    # Special handling for login - redirect to our SSO
    if path.startswith('login'):
        return redirect('/manager/')

    try:
        # Forward request to Grafana
        proxy_response = grafana_proxy.make_request(
            path,
            method=request.method,
            params=request.query_string,
            json=request.json if request.method in ['POST', 'PUT'] else None,
            headers={'Content-Type': request.headers.get('Content-Type', '')}
        )

        # Set response status and headers
        response.status = proxy_response.status_code

        # Handle different content types
        content_type = proxy_response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            response.headers['Content-Type'] = 'application/json'
            return proxy_response.json() if proxy_response.text else {}
        elif 'text/html' in content_type:
            # Modify HTML to inject our authentication and styling
            html_content = proxy_response.text
            # TODO: Inject SSO authentication scripts
            response.headers['Content-Type'] = 'text/html'
            return html_content
        else:
            response.headers['Content-Type'] = content_type
            return proxy_response.content

    except Exception as e:
        response.status = 500
        return {'error': f'Grafana proxy error: {str(e)}'}

# Kibana Proxy Endpoints
@action('kibana')
@action('kibana/<path:path>')
def kibana_proxy_handler(path=''):
    """Proxy requests to Kibana with authentication"""
    # TODO: Add proper user authentication check

    if not path:
        return redirect('/manager/kibana/app/home')

    try:
        proxy_response = kibana_proxy.make_request(
            path,
            method=request.method,
            params=request.query_string,
            json=request.json if request.method in ['POST', 'PUT'] else None
        )

        response.status = proxy_response.status_code
        content_type = proxy_response.headers.get('Content-Type', '')

        if 'application/json' in content_type:
            response.headers['Content-Type'] = 'application/json'
            return proxy_response.json() if proxy_response.text else {}
        elif 'text/html' in content_type:
            response.headers['Content-Type'] = 'text/html'
            return proxy_response.text
        else:
            response.headers['Content-Type'] = content_type
            return proxy_response.content

    except Exception as e:
        response.status = 500
        return {'error': f'Kibana proxy error: {str(e)}'}

# Prometheus Proxy Endpoints
@action('prometheus')
@action('prometheus/<path:path>')
def prometheus_proxy_handler(path=''):
    """Proxy requests to Prometheus"""
    # TODO: Add proper user authentication check

    if not path:
        return redirect('/manager/prometheus/graph')

    try:
        proxy_response = prometheus_proxy.make_request(
            path,
            method=request.method,
            params=request.query_string
        )

        response.status = proxy_response.status_code
        content_type = proxy_response.headers.get('Content-Type', '')

        if 'application/json' in content_type:
            response.headers['Content-Type'] = 'application/json'
            return proxy_response.json() if proxy_response.text else {}
        elif 'text/html' in content_type:
            response.headers['Content-Type'] = 'text/html'
            return proxy_response.text
        else:
            response.headers['Content-Type'] = content_type
            return proxy_response.content

    except Exception as e:
        response.status = 500
        return {'error': f'Prometheus proxy error: {str(e)}'}

# Elasticsearch Proxy Endpoints (Admin only)
@action('elasticsearch')
@action('elasticsearch/<path:path>')
def elasticsearch_proxy_handler(path=''):
    """Proxy requests to Elasticsearch (admin access only)"""
    # TODO: Add admin user authentication check

    try:
        proxy_response = elasticsearch_proxy.make_request(
            path,
            method=request.method,
            params=request.query_string,
            json=request.json if request.method in ['POST', 'PUT'] else None
        )

        response.status = proxy_response.status_code
        response.headers['Content-Type'] = 'application/json'

        return proxy_response.json() if proxy_response.text else {}

    except Exception as e:
        response.status = 500
        return {'error': f'Elasticsearch proxy error: {str(e)}'}

# AlertManager Proxy Endpoints
@action('alerts')
@action('alerts/<path:path>')
def alertmanager_proxy_handler(path=''):
    """Proxy requests to AlertManager"""
    # TODO: Add proper user authentication check

    if not path:
        return redirect('/manager/alerts/#/alerts')

    try:
        proxy_response = alertmanager_proxy.make_request(
            path,
            method=request.method,
            params=request.query_string,
            json=request.json if request.method in ['POST', 'PUT'] else None
        )

        response.status = proxy_response.status_code
        content_type = proxy_response.headers.get('Content-Type', '')

        if 'application/json' in content_type:
            response.headers['Content-Type'] = 'application/json'
            return proxy_response.json() if proxy_response.text else {}
        elif 'text/html' in content_type:
            response.headers['Content-Type'] = 'text/html'
            return proxy_response.text
        else:
            response.headers['Content-Type'] = content_type
            return proxy_response.content

    except Exception as e:
        response.status = 500
        return {'error': f'AlertManager proxy error: {str(e)}'}

# Service Health Check Endpoints
@action('services/health')
@action.uses(CORS())
def services_health():
    """Check health of all integrated services"""
    services = {
        'grafana': {'url': GRAFANA_URL, 'proxy': grafana_proxy},
        'kibana': {'url': KIBANA_URL, 'proxy': kibana_proxy},
        'prometheus': {'url': PROMETHEUS_URL, 'proxy': prometheus_proxy},
        'elasticsearch': {'url': ELASTICSEARCH_URL, 'proxy': elasticsearch_proxy},
        'alertmanager': {'url': ALERTMANAGER_URL, 'proxy': alertmanager_proxy},
        'fleet': {'url': FLEET_URL, 'proxy': fleet_proxy}
    }

    health_status = {}

    for service_name, service_info in services.items():
        try:
            # Use appropriate health check endpoint for each service
            health_path = {
                'grafana': 'api/health',
                'kibana': 'api/status',
                'prometheus': '-/healthy',
                'elasticsearch': '_cluster/health',
                'alertmanager': '-/healthy',
                'fleet': 'healthz'
            }.get(service_name, '')

            proxy_response = service_info['proxy'].make_request(health_path, timeout=5)

            health_status[service_name] = {
                'status': 'healthy' if proxy_response.status_code == 200 else 'unhealthy',
                'status_code': proxy_response.status_code,
                'url': service_info['url'],
                'response_time_ms': proxy_response.elapsed.total_seconds() * 1000 if hasattr(proxy_response, 'elapsed') else 0
            }

        except Exception as e:
            health_status[service_name] = {
                'status': 'error',
                'error': str(e),
                'url': service_info['url'],
                'response_time_ms': 0
            }

    # Overall health
    healthy_services = sum(1 for s in health_status.values() if s['status'] == 'healthy')
    total_services = len(services)

    return {
        'overall_status': 'healthy' if healthy_services == total_services else 'degraded',
        'healthy_services': healthy_services,
        'total_services': total_services,
        'services': health_status
    }

# Service configuration endpoint
@action('services/config')
@action.uses(CORS())
def services_config():
    """Get configuration information for all services"""
    # TODO: Add admin authentication check

    return {
        'services': {
            'grafana': {
                'name': 'Grafana',
                'description': 'Metrics visualization and dashboards',
                'url': '/manager/grafana',
                'external_url': GRAFANA_URL,
                'icon': '📊'
            },
            'kibana': {
                'name': 'Kibana',
                'description': 'Log search and analysis',
                'url': '/manager/kibana',
                'external_url': KIBANA_URL,
                'icon': '📋'
            },
            'prometheus': {
                'name': 'Prometheus',
                'description': 'Metrics collection and querying',
                'url': '/manager/prometheus',
                'external_url': PROMETHEUS_URL,
                'icon': '🔍'
            },
            'fleet': {
                'name': 'Fleet',
                'description': 'Device management and osquery',
                'url': '/manager/fleet',
                'external_url': FLEET_URL,
                'icon': '🛡️'
            },
            'alertmanager': {
                'name': 'AlertManager',
                'description': 'Alert routing and management',
                'url': '/manager/alerts',
                'external_url': ALERTMANAGER_URL,
                'icon': '🚨'
            }
        },
        'enterprise_services': {
            'ai_analysis': {
                'name': 'AI Analysis',
                'description': 'Intelligent metrics analysis and recommendations',
                'url': '/manager/ai',
                'icon': '🤖',
                'requires_license': True
            }
        }
    }