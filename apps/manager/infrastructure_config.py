#!/usr/bin/env python3
"""
KillKrill Infrastructure Configuration APIs
Provides REST APIs to configure Prometheus, Elasticsearch, and KillKrill components
"""

import os
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import yaml
from py4web import action, request, response
from py4web.utils.cors import CORS
from shared.auth.middleware import require_auth
import structlog

logger = structlog.get_logger()

# Configuration for infrastructure services
PROMETHEUS_BASE_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
ELASTICSEARCH_BASE_URL = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
KIBANA_BASE_URL = os.getenv('KIBANA_URL', 'http://kibana:5601')
GRAFANA_BASE_URL = os.getenv('GRAFANA_URL', 'http://grafana:3000')
ALERTMANAGER_BASE_URL = os.getenv('ALERTMANAGER_URL', 'http://alertmanager:9093')


class PrometheusConfigAPI:
    """Prometheus configuration management via API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = 30

    def get_config(self) -> Dict[str, Any]:
        """Get current Prometheus configuration"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/status/config", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Prometheus config", error=str(e))
            raise

    def reload_config(self) -> Dict[str, Any]:
        """Reload Prometheus configuration"""
        try:
            response = requests.post(f"{self.base_url}/-/reload", timeout=self.timeout)
            response.raise_for_status()
            return {"status": "success", "message": "Configuration reloaded"}
        except Exception as e:
            logger.error("Failed to reload Prometheus config", error=str(e))
            raise

    def get_targets(self) -> Dict[str, Any]:
        """Get scrape targets"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/targets", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Prometheus targets", error=str(e))
            raise

    def get_rules(self) -> Dict[str, Any]:
        """Get alerting rules"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/rules", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Prometheus rules", error=str(e))
            raise

    def get_alerts(self) -> Dict[str, Any]:
        """Get active alerts"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/alerts", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Prometheus alerts", error=str(e))
            raise

    def get_metrics(self) -> List[str]:
        """Get available metrics"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/label/__name__/values", timeout=self.timeout)
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            logger.error("Failed to get Prometheus metrics", error=str(e))
            raise

    def query(self, query: str, time: Optional[str] = None) -> Dict[str, Any]:
        """Execute Prometheus query"""
        try:
            params = {'query': query}
            if time:
                params['time'] = time

            response = requests.get(f"{self.base_url}/api/v1/query",
                                  params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to execute Prometheus query", query=query, error=str(e))
            raise

    def query_range(self, query: str, start: str, end: str, step: str) -> Dict[str, Any]:
        """Execute Prometheus range query"""
        try:
            params = {
                'query': query,
                'start': start,
                'end': end,
                'step': step
            }

            response = requests.get(f"{self.base_url}/api/v1/query_range",
                                  params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to execute Prometheus range query", query=query, error=str(e))
            raise


class ElasticsearchConfigAPI:
    """Elasticsearch configuration management via API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = 30

    def get_cluster_health(self) -> Dict[str, Any]:
        """Get cluster health"""
        try:
            response = requests.get(f"{self.base_url}/_cluster/health", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Elasticsearch cluster health", error=str(e))
            raise

    def get_cluster_settings(self) -> Dict[str, Any]:
        """Get cluster settings"""
        try:
            response = requests.get(f"{self.base_url}/_cluster/settings", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Elasticsearch cluster settings", error=str(e))
            raise

    def update_cluster_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update cluster settings"""
        try:
            response = requests.put(f"{self.base_url}/_cluster/settings",
                                  json=settings, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to update Elasticsearch cluster settings", error=str(e))
            raise

    def get_indices(self) -> Dict[str, Any]:
        """Get indices information"""
        try:
            response = requests.get(f"{self.base_url}/_cat/indices?format=json", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Elasticsearch indices", error=str(e))
            raise

    def get_index_templates(self) -> Dict[str, Any]:
        """Get index templates"""
        try:
            response = requests.get(f"{self.base_url}/_index_template", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Elasticsearch index templates", error=str(e))
            raise

    def create_index_template(self, name: str, template: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update index template"""
        try:
            response = requests.put(f"{self.base_url}/_index_template/{name}",
                                  json=template, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to create Elasticsearch index template", name=name, error=str(e))
            raise

    def get_ilm_policies(self) -> Dict[str, Any]:
        """Get ILM policies"""
        try:
            response = requests.get(f"{self.base_url}/_ilm/policy", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Elasticsearch ILM policies", error=str(e))
            raise

    def create_ilm_policy(self, name: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update ILM policy"""
        try:
            response = requests.put(f"{self.base_url}/_ilm/policy/{name}",
                                  json=policy, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to create Elasticsearch ILM policy", name=name, error=str(e))
            raise

    def search(self, index: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search query"""
        try:
            response = requests.post(f"{self.base_url}/{index}/_search",
                                   json=query, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to execute Elasticsearch search", index=index, error=str(e))
            raise

    def get_mappings(self, index: str) -> Dict[str, Any]:
        """Get index mappings"""
        try:
            response = requests.get(f"{self.base_url}/{index}/_mapping", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Elasticsearch mappings", index=index, error=str(e))
            raise

    def update_mapping(self, index: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Update index mapping"""
        try:
            response = requests.put(f"{self.base_url}/{index}/_mapping",
                                  json=mapping, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to update Elasticsearch mapping", index=index, error=str(e))
            raise


class KibanaConfigAPI:
    """Kibana configuration management via API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = 30

    def get_status(self) -> Dict[str, Any]:
        """Get Kibana status"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Kibana status", error=str(e))
            raise

    def get_index_patterns(self) -> Dict[str, Any]:
        """Get index patterns"""
        try:
            headers = {'kbn-xsrf': 'true'}
            response = requests.get(f"{self.base_url}/api/saved_objects/_find?type=index-pattern",
                                  headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Kibana index patterns", error=str(e))
            raise

    def create_index_pattern(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Create index pattern"""
        try:
            headers = {'kbn-xsrf': 'true', 'Content-Type': 'application/json'}
            response = requests.post(f"{self.base_url}/api/saved_objects/index-pattern",
                                   json=pattern, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to create Kibana index pattern", error=str(e))
            raise

    def get_dashboards(self) -> Dict[str, Any]:
        """Get dashboards"""
        try:
            headers = {'kbn-xsrf': 'true'}
            response = requests.get(f"{self.base_url}/api/saved_objects/_find?type=dashboard",
                                  headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Kibana dashboards", error=str(e))
            raise


class GrafanaConfigAPI:
    """Grafana configuration management via API"""

    def __init__(self, base_url: str, username: str = 'admin', password: str = 'admin'):
        self.base_url = base_url.rstrip('/')
        self.auth = (username, password)
        self.timeout = 30

    def get_health(self) -> Dict[str, Any]:
        """Get Grafana health"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Grafana health", error=str(e))
            raise

    def get_datasources(self) -> List[Dict[str, Any]]:
        """Get data sources"""
        try:
            response = requests.get(f"{self.base_url}/api/datasources",
                                  auth=self.auth, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Grafana datasources", error=str(e))
            raise

    def create_datasource(self, datasource: Dict[str, Any]) -> Dict[str, Any]:
        """Create data source"""
        try:
            response = requests.post(f"{self.base_url}/api/datasources",
                                   json=datasource, auth=self.auth, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to create Grafana datasource", error=str(e))
            raise

    def get_dashboards(self) -> List[Dict[str, Any]]:
        """Get dashboards"""
        try:
            response = requests.get(f"{self.base_url}/api/search?type=dash-db",
                                  auth=self.auth, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get Grafana dashboards", error=str(e))
            raise

    def create_dashboard(self, dashboard: Dict[str, Any]) -> Dict[str, Any]:
        """Create dashboard"""
        try:
            response = requests.post(f"{self.base_url}/api/dashboards/db",
                                   json=dashboard, auth=self.auth, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to create Grafana dashboard", error=str(e))
            raise


# Initialize API clients
prometheus_api = PrometheusConfigAPI(PROMETHEUS_BASE_URL)
elasticsearch_api = ElasticsearchConfigAPI(ELASTICSEARCH_BASE_URL)
kibana_api = KibanaConfigAPI(KIBANA_BASE_URL)
grafana_api = GrafanaConfigAPI(GRAFANA_BASE_URL,
                              os.getenv('GRAFANA_USER', 'admin'),
                              os.getenv('GRAFANA_PASSWORD', 'admin'))


# =============================================================================
# REST API Endpoints for Infrastructure Configuration
# =============================================================================

# Prometheus Configuration APIs
@action('api/v1/config/prometheus/status', method=['GET'])
@CORS()
@require_auth()
def prometheus_status(current_user=None):
    """Get Prometheus status and configuration"""
    try:
        config = prometheus_api.get_config()
        targets = prometheus_api.get_targets()
        rules = prometheus_api.get_rules()
        alerts = prometheus_api.get_alerts()

        return {
            'status': 'success',
            'data': {
                'config': config,
                'targets': targets,
                'rules': rules,
                'alerts': alerts,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get Prometheus status: {str(e)}'}


@action('api/v1/config/prometheus/reload', method=['POST'])
@CORS()
@require_auth()
def prometheus_reload(current_user=None):
    """Reload Prometheus configuration"""
    try:
        result = prometheus_api.reload_config()
        return result
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to reload Prometheus config: {str(e)}'}


@action('api/v1/config/prometheus/query', method=['POST'])
@CORS()
@require_auth()
def prometheus_query(current_user=None):
    """Execute Prometheus query"""
    try:
        data = request.json
        query = data.get('query')
        time_param = data.get('time')

        if not query:
            response.status = 400
            return {'error': 'Query parameter is required'}

        if data.get('range'):
            # Range query
            start = data.get('start')
            end = data.get('end')
            step = data.get('step', '1m')

            if not start or not end:
                response.status = 400
                return {'error': 'Start and end parameters required for range query'}

            result = prometheus_api.query_range(query, start, end, step)
        else:
            # Instant query
            result = prometheus_api.query(query, time_param)

        return {
            'status': 'success',
            'data': result
        }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to execute Prometheus query: {str(e)}'}


# Elasticsearch Configuration APIs
@action('api/v1/config/elasticsearch/cluster', method=['GET'])
@CORS()
@require_auth()
def elasticsearch_cluster_info(current_user=None):
    """Get Elasticsearch cluster information"""
    try:
        health = elasticsearch_api.get_cluster_health()
        settings = elasticsearch_api.get_cluster_settings()
        indices = elasticsearch_api.get_indices()

        return {
            'status': 'success',
            'data': {
                'health': health,
                'settings': settings,
                'indices': indices,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get Elasticsearch cluster info: {str(e)}'}


@action('api/v1/config/elasticsearch/settings', method=['GET', 'PUT'])
@CORS()
@require_auth()
def elasticsearch_cluster_settings(current_user=None):
    """Get or update Elasticsearch cluster settings"""
    try:
        if request.method == 'GET':
            result = elasticsearch_api.get_cluster_settings()
            return {
                'status': 'success',
                'data': result
            }
        elif request.method == 'PUT':
            settings = request.json
            if not settings:
                response.status = 400
                return {'error': 'Settings data is required'}

            result = elasticsearch_api.update_cluster_settings(settings)
            return {
                'status': 'success',
                'data': result
            }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to manage Elasticsearch settings: {str(e)}'}


@action('api/v1/config/elasticsearch/templates', method=['GET', 'POST'])
@CORS()
@require_auth()
def elasticsearch_index_templates(current_user=None):
    """Get or create Elasticsearch index templates"""
    try:
        if request.method == 'GET':
            result = elasticsearch_api.get_index_templates()
            return {
                'status': 'success',
                'data': result
            }
        elif request.method == 'POST':
            data = request.json
            name = data.get('name')
            template = data.get('template')

            if not name or not template:
                response.status = 400
                return {'error': 'Name and template data are required'}

            result = elasticsearch_api.create_index_template(name, template)
            return {
                'status': 'success',
                'data': result
            }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to manage Elasticsearch templates: {str(e)}'}


@action('api/v1/config/elasticsearch/ilm', method=['GET', 'POST'])
@CORS()
@require_auth()
def elasticsearch_ilm_policies(current_user=None):
    """Get or create Elasticsearch ILM policies"""
    try:
        if request.method == 'GET':
            result = elasticsearch_api.get_ilm_policies()
            return {
                'status': 'success',
                'data': result
            }
        elif request.method == 'POST':
            data = request.json
            name = data.get('name')
            policy = data.get('policy')

            if not name or not policy:
                response.status = 400
                return {'error': 'Name and policy data are required'}

            result = elasticsearch_api.create_ilm_policy(name, policy)
            return {
                'status': 'success',
                'data': result
            }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to manage Elasticsearch ILM policies: {str(e)}'}


@action('api/v1/config/elasticsearch/search', method=['POST'])
@CORS()
@require_auth()
def elasticsearch_search(current_user=None):
    """Execute Elasticsearch search"""
    try:
        data = request.json
        index = data.get('index', 'killkrill-logs-*')
        query = data.get('query', {})

        result = elasticsearch_api.search(index, query)
        return {
            'status': 'success',
            'data': result
        }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to execute Elasticsearch search: {str(e)}'}


# Kibana Configuration APIs
@action('api/v1/config/kibana/status', method=['GET'])
@CORS()
@require_auth()
def kibana_status(current_user=None):
    """Get Kibana status"""
    try:
        status = kibana_api.get_status()
        index_patterns = kibana_api.get_index_patterns()
        dashboards = kibana_api.get_dashboards()

        return {
            'status': 'success',
            'data': {
                'status': status,
                'index_patterns': index_patterns,
                'dashboards': dashboards,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get Kibana status: {str(e)}'}


# Grafana Configuration APIs
@action('api/v1/config/grafana/status', method=['GET'])
@CORS()
@require_auth()
def grafana_status(current_user=None):
    """Get Grafana status"""
    try:
        health = grafana_api.get_health()
        datasources = grafana_api.get_datasources()
        dashboards = grafana_api.get_dashboards()

        return {
            'status': 'success',
            'data': {
                'health': health,
                'datasources': datasources,
                'dashboards': dashboards,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get Grafana status: {str(e)}'}


@action('api/v1/config/grafana/datasources', method=['GET', 'POST'])
@CORS()
@require_auth()
def grafana_datasources(current_user=None):
    """Get or create Grafana data sources"""
    try:
        if request.method == 'GET':
            result = grafana_api.get_datasources()
            return {
                'status': 'success',
                'data': result
            }
        elif request.method == 'POST':
            datasource = request.json
            if not datasource:
                response.status = 400
                return {'error': 'Datasource data is required'}

            result = grafana_api.create_datasource(datasource)
            return {
                'status': 'success',
                'data': result
            }
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to manage Grafana datasources: {str(e)}'}


# Infrastructure Overview API
@action('api/v1/config/infrastructure/overview', method=['GET'])
@CORS()
@require_auth()
def infrastructure_overview(current_user=None):
    """Get comprehensive infrastructure overview"""
    try:
        # Gather status from all components
        overview = {
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }

        # Prometheus
        try:
            prom_config = prometheus_api.get_config()
            prom_targets = prometheus_api.get_targets()
            overview['components']['prometheus'] = {
                'status': 'healthy',
                'config_version': prom_config.get('data', {}).get('yaml', {}).get('__version__', 'unknown'),
                'targets_up': len([t for t in prom_targets.get('data', {}).get('activeTargets', []) if t.get('health') == 'up']),
                'targets_total': len(prom_targets.get('data', {}).get('activeTargets', []))
            }
        except Exception as e:
            overview['components']['prometheus'] = {
                'status': 'error',
                'error': str(e)
            }

        # Elasticsearch
        try:
            es_health = elasticsearch_api.get_cluster_health()
            es_indices = elasticsearch_api.get_indices()
            overview['components']['elasticsearch'] = {
                'status': es_health.get('status', 'unknown'),
                'cluster_name': es_health.get('cluster_name'),
                'nodes': es_health.get('number_of_nodes', 0),
                'indices_count': len(es_indices) if isinstance(es_indices, list) else 0,
                'shards': {
                    'active': es_health.get('active_shards', 0),
                    'relocating': es_health.get('relocating_shards', 0),
                    'unassigned': es_health.get('unassigned_shards', 0)
                }
            }
        except Exception as e:
            overview['components']['elasticsearch'] = {
                'status': 'error',
                'error': str(e)
            }

        # Kibana
        try:
            kibana_status_data = kibana_api.get_status()
            overview['components']['kibana'] = {
                'status': kibana_status_data.get('status', {}).get('overall', {}).get('state', 'unknown'),
                'version': kibana_status_data.get('version', {}).get('number', 'unknown')
            }
        except Exception as e:
            overview['components']['kibana'] = {
                'status': 'error',
                'error': str(e)
            }

        # Grafana
        try:
            grafana_health_data = grafana_api.get_health()
            overview['components']['grafana'] = {
                'status': 'healthy' if grafana_health_data.get('database') == 'ok' else 'degraded',
                'database': grafana_health_data.get('database', 'unknown'),
                'version': grafana_health_data.get('version', 'unknown')
            }
        except Exception as e:
            overview['components']['grafana'] = {
                'status': 'error',
                'error': str(e)
            }

        return {
            'status': 'success',
            'data': overview
        }

    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get infrastructure overview: {str(e)}'}