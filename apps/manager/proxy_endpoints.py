#!/usr/bin/env python3
"""
KillKrill Infrastructure Proxy Endpoints
Provides proxy access to infrastructure services for embedded views
"""

import os
import logging
import requests
from urllib.parse import urljoin, urlparse
from py4web import action, request, response
from py4web.utils.cors import CORS
from shared.auth.middleware import require_auth
import structlog

logger = structlog.get_logger()

# Infrastructure service URLs
PROMETHEUS_BASE_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
ELASTICSEARCH_BASE_URL = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
KIBANA_BASE_URL = os.getenv('KIBANA_URL', 'http://kibana:5601')
GRAFANA_BASE_URL = os.getenv('GRAFANA_URL', 'http://grafana:3000')
ALERTMANAGER_BASE_URL = os.getenv('ALERTMANAGER_URL', 'http://alertmanager:9093')

# Proxy configuration
PROXY_TIMEOUT = 30
ALLOWED_CONTENT_TYPES = [
    'text/html', 'text/css', 'text/javascript', 'application/javascript',
    'application/json', 'image/png', 'image/jpeg', 'image/gif', 'image/svg+xml',
    'font/woff', 'font/woff2', 'application/font-woff', 'application/font-woff2'
]


def create_proxy_handler(service_name: str, base_url: str):
    """Create a proxy handler for a specific service"""

    @action(f'proxy/{service_name}', method=['GET', 'POST', 'PUT', 'DELETE'])
    @action(f'proxy/{service_name}/<path:path>', method=['GET', 'POST', 'PUT', 'DELETE'])
    @CORS()
    @require_auth()
    def proxy_handler(path='', current_user=None):
        """Proxy requests to the infrastructure service"""
        try:
            # Build target URL
            if path:
                target_url = urljoin(base_url.rstrip('/') + '/', path)
            else:
                target_url = base_url

            # Forward query parameters
            if request.query_string:
                target_url += '?' + request.query_string

            # Prepare headers (exclude host and connection headers)
            headers = {}
            for key, value in request.headers.items():
                if key.lower() not in ['host', 'connection', 'content-length', 'transfer-encoding']:
                    headers[key] = value

            # Add authentication headers for services that need them
            if service_name == 'grafana':
                # Add basic auth for Grafana
                grafana_user = os.getenv('GRAFANA_USER', 'admin')
                grafana_password = os.getenv('GRAFANA_PASSWORD', 'admin')
                headers['Authorization'] = f'Basic {grafana_user}:{grafana_password}'

            # Forward the request
            if request.method == 'GET':
                resp = requests.get(target_url, headers=headers, timeout=PROXY_TIMEOUT, stream=True)
            elif request.method == 'POST':
                resp = requests.post(target_url, headers=headers, data=request.body.read(), timeout=PROXY_TIMEOUT, stream=True)
            elif request.method == 'PUT':
                resp = requests.put(target_url, headers=headers, data=request.body.read(), timeout=PROXY_TIMEOUT, stream=True)
            elif request.method == 'DELETE':
                resp = requests.delete(target_url, headers=headers, timeout=PROXY_TIMEOUT, stream=True)
            else:
                response.status = 405
                return {'error': 'Method not allowed'}

            # Set response headers
            for key, value in resp.headers.items():
                if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'connection']:
                    response.headers[key] = value

            # Set response status
            response.status = resp.status_code

            # Handle different content types
            content_type = resp.headers.get('content-type', '').lower()

            # For HTML content, modify to work in iframe
            if 'text/html' in content_type:
                content = resp.text

                # Inject base tag to fix relative URLs
                base_tag = f'<base href="{base_url}/" target="_parent">'
                if '<head>' in content:
                    content = content.replace('<head>', f'<head>{base_tag}')
                elif '<html>' in content:
                    content = content.replace('<html>', f'<html><head>{base_tag}</head>')
                else:
                    content = base_tag + content

                # Add iframe-specific styles
                iframe_styles = """
                <style>
                    /* Hide elements that don't work well in iframes */
                    .navbar-nav .nav-link[href*="logout"] { display: none !important; }
                    .navbar-brand { pointer-events: none; }

                    /* Ensure content fits in iframe */
                    body {
                        margin: 0 !important;
                        padding: 10px !important;
                        overflow-x: auto !important;
                    }

                    /* Fix Grafana iframe issues */
                    .sidemenu { position: relative !important; }
                    .main-view { margin-left: 0 !important; }

                    /* Fix Kibana iframe issues */
                    .kbnTopNavMenu { position: relative !important; }

                    /* Fix Prometheus iframe issues */
                    .navbar-fixed-top { position: relative !important; }
                </style>
                """

                if '</head>' in content:
                    content = content.replace('</head>', f'{iframe_styles}</head>')
                else:
                    content = iframe_styles + content

                return content

            # For other content types, stream the response
            else:
                def generate():
                    for chunk in resp.iter_content(chunk_size=8192):
                        yield chunk

                return generate()

        except requests.exceptions.Timeout:
            response.status = 504
            return {'error': f'Timeout connecting to {service_name}'}
        except requests.exceptions.ConnectionError:
            response.status = 503
            return {'error': f'Unable to connect to {service_name}'}
        except Exception as e:
            logger.error(f"Proxy error for {service_name}", error=str(e))
            response.status = 500
            return {'error': f'Proxy error: {str(e)}'}

    return proxy_handler


# Create proxy handlers for each service
prometheus_proxy = create_proxy_handler('prometheus', PROMETHEUS_BASE_URL)
grafana_proxy = create_proxy_handler('grafana', GRAFANA_BASE_URL)
elasticsearch_proxy = create_proxy_handler('elasticsearch', ELASTICSEARCH_BASE_URL)
kibana_proxy = create_proxy_handler('kibana', KIBANA_BASE_URL)
alertmanager_proxy = create_proxy_handler('alertmanager', ALERTMANAGER_BASE_URL)


@action('api/v1/infrastructure/endpoints', method=['GET'])
@CORS()
@require_auth()
def get_infrastructure_endpoints(current_user=None):
    """Get infrastructure service endpoints"""
    try:
        endpoints = {
            'prometheus': {
                'internal': PROMETHEUS_BASE_URL,
                'proxy': '/proxy/prometheus',
                'external': request.url_root.rstrip('/') + '/proxy/prometheus',
                'status': 'unknown'
            },
            'grafana': {
                'internal': GRAFANA_BASE_URL,
                'proxy': '/proxy/grafana',
                'external': request.url_root.rstrip('/') + '/proxy/grafana',
                'status': 'unknown'
            },
            'elasticsearch': {
                'internal': ELASTICSEARCH_BASE_URL,
                'proxy': '/proxy/elasticsearch',
                'external': request.url_root.rstrip('/') + '/proxy/elasticsearch',
                'status': 'unknown'
            },
            'kibana': {
                'internal': KIBANA_BASE_URL,
                'proxy': '/proxy/kibana',
                'external': request.url_root.rstrip('/') + '/proxy/kibana',
                'status': 'unknown'
            },
            'alertmanager': {
                'internal': ALERTMANAGER_BASE_URL,
                'proxy': '/proxy/alertmanager',
                'external': request.url_root.rstrip('/') + '/proxy/alertmanager',
                'status': 'unknown'
            }
        }

        # Check service availability
        for service, config in endpoints.items():
            try:
                resp = requests.get(config['internal'], timeout=5)
                config['status'] = 'healthy' if resp.status_code == 200 else 'unhealthy'
            except:
                config['status'] = 'unreachable'

        return {
            'status': 'success',
            'data': {
                'endpoints': endpoints,
                'timestamp': datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get infrastructure endpoints: {str(e)}'}


@action('infrastructure', method=['GET'])
@require_auth()
def infrastructure_dashboard(current_user=None):
    """Render the infrastructure management dashboard"""
    return dict(current_user=current_user)


@action('api/v1/infrastructure/health', method=['GET'])
@CORS()
@require_auth()
def infrastructure_health(current_user=None):
    """Get health status of all infrastructure services"""
    try:
        health_status = {}

        services = {
            'prometheus': PROMETHEUS_BASE_URL,
            'grafana': GRAFANA_BASE_URL,
            'elasticsearch': ELASTICSEARCH_BASE_URL,
            'kibana': KIBANA_BASE_URL,
            'alertmanager': ALERTMANAGER_BASE_URL
        }

        for service, url in services.items():
            try:
                # Use appropriate health endpoint for each service
                if service == 'prometheus':
                    health_url = f"{url}/-/ready"
                elif service == 'grafana':
                    health_url = f"{url}/api/health"
                elif service == 'elasticsearch':
                    health_url = f"{url}/_cluster/health"
                elif service == 'kibana':
                    health_url = f"{url}/api/status"
                elif service == 'alertmanager':
                    health_url = f"{url}/-/ready"
                else:
                    health_url = url

                resp = requests.get(health_url, timeout=10)

                if resp.status_code == 200:
                    health_status[service] = {
                        'status': 'healthy',
                        'response_time': resp.elapsed.total_seconds(),
                        'details': resp.json() if service in ['grafana', 'elasticsearch', 'kibana'] else None
                    }
                else:
                    health_status[service] = {
                        'status': 'unhealthy',
                        'status_code': resp.status_code,
                        'details': resp.text[:200] if resp.text else None
                    }

            except requests.exceptions.Timeout:
                health_status[service] = {
                    'status': 'timeout',
                    'error': 'Request timeout'
                }
            except requests.exceptions.ConnectionError:
                health_status[service] = {
                    'status': 'unreachable',
                    'error': 'Connection refused'
                }
            except Exception as e:
                health_status[service] = {
                    'status': 'error',
                    'error': str(e)
                }

        # Calculate overall health
        healthy_count = sum(1 for status in health_status.values() if status['status'] == 'healthy')
        total_count = len(health_status)

        overall_status = 'healthy' if healthy_count == total_count else \
                        'degraded' if healthy_count > 0 else 'unhealthy'

        return {
            'status': 'success',
            'data': {
                'overall_status': overall_status,
                'healthy_services': healthy_count,
                'total_services': total_count,
                'services': health_status,
                'timestamp': datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get infrastructure health: {str(e)}'}