"""
KillKrill API - Infrastructure Integration Tests
httpx-based integration tests for infrastructure endpoints with pytest markers.
Compatible with Quart async patterns via pytest-asyncio.
"""

import httpx
import pytest


@pytest.mark.integration
class TestPrometheusEndpoints:
    """Test Prometheus integration endpoints"""

    def test_prometheus_status(self, api_client, auth_headers):
        """Test Prometheus status endpoint"""
        response = api_client.get(
            "/infrastructure/prometheus/status", headers=auth_headers
        )
        assert response.status_code in [200, 503]

    def test_prometheus_query(self, api_client, auth_headers):
        """Test Prometheus query endpoint"""
        payload = {"query": "up"}
        response = api_client.post(
            "/infrastructure/prometheus/query", headers=auth_headers, json=payload
        )
        assert response.status_code in [200, 400, 503]

    def test_prometheus_targets(self, api_client, auth_headers):
        """Test Prometheus targets endpoint"""
        response = api_client.get(
            "/infrastructure/prometheus/targets", headers=auth_headers
        )
        assert response.status_code in [200, 503]


@pytest.mark.integration
class TestElasticsearchEndpoints:
    """Test Elasticsearch integration endpoints"""

    def test_elasticsearch_status(self, api_client, auth_headers):
        """Test Elasticsearch cluster status"""
        response = api_client.get(
            "/infrastructure/elasticsearch/status", headers=auth_headers
        )
        assert response.status_code in [200, 503]

    def test_elasticsearch_indices(self, api_client, auth_headers):
        """Test Elasticsearch indices listing"""
        response = api_client.get(
            "/infrastructure/elasticsearch/indices", headers=auth_headers
        )
        assert response.status_code in [200, 503]

    def test_elasticsearch_search(self, api_client, auth_headers):
        """Test Elasticsearch search endpoint"""
        payload = {"index": "logs", "query": {"match_all": {}}}
        response = api_client.post(
            "/infrastructure/elasticsearch/search", headers=auth_headers, json=payload
        )
        assert response.status_code in [200, 400, 503]


@pytest.mark.integration
class TestGrafanaEndpoints:
    """Test Grafana integration endpoints"""

    def test_grafana_status(self, api_client, auth_headers):
        """Test Grafana health status"""
        response = api_client.get(
            "/infrastructure/grafana/status", headers=auth_headers
        )
        assert response.status_code in [200, 503]

    def test_grafana_dashboards(self, api_client, auth_headers):
        """Test Grafana dashboards listing"""
        response = api_client.get(
            "/infrastructure/grafana/dashboards", headers=auth_headers
        )
        assert response.status_code in [200, 503]

    def test_grafana_datasources(self, api_client, auth_headers):
        """Test Grafana datasources listing"""
        response = api_client.get(
            "/infrastructure/grafana/datasources", headers=auth_headers
        )
        assert response.status_code in [200, 503]


@pytest.mark.integration
class TestKibanaEndpoints:
    """Test Kibana integration endpoints"""

    def test_kibana_status(self, api_client, auth_headers):
        """Test Kibana status endpoint"""
        response = api_client.get("/infrastructure/kibana/status", headers=auth_headers)
        assert response.status_code in [200, 503]

    def test_kibana_index_patterns(self, api_client, auth_headers):
        """Test Kibana index patterns listing"""
        response = api_client.get(
            "/infrastructure/kibana/index-patterns", headers=auth_headers
        )
        assert response.status_code in [200, 503]


@pytest.mark.integration
class TestAlertManagerEndpoints:
    """Test AlertManager integration endpoints"""

    def test_alertmanager_status(self, api_client, auth_headers):
        """Test AlertManager status endpoint"""
        response = api_client.get(
            "/infrastructure/alertmanager/status", headers=auth_headers
        )
        assert response.status_code in [200, 503]

    def test_alertmanager_alerts(self, api_client, auth_headers):
        """Test AlertManager alerts listing"""
        response = api_client.get(
            "/infrastructure/alertmanager/alerts", headers=auth_headers
        )
        assert response.status_code in [200, 503]

    def test_alertmanager_silences(self, api_client, auth_headers):
        """Test AlertManager silences listing"""
        response = api_client.get(
            "/infrastructure/alertmanager/silences", headers=auth_headers
        )
        assert response.status_code in [200, 503]


@pytest.mark.integration
class TestInfrastructureHealthCheck:
    """Test infrastructure health check endpoints"""

    def test_health_check(self, api_client, auth_headers):
        """Test infrastructure health check"""
        response = api_client.get("/infrastructure/health", headers=auth_headers)
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data or "services" in data
