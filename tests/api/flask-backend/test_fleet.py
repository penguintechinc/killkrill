"""
KillKrill API - Fleet Integration Tests
httpx-based integration tests for fleet endpoints with pytest markers.
Compatible with Quart async patterns via pytest-asyncio.
"""

import pytest
import httpx


@pytest.mark.integration
class TestFleetStatus:
    """Test GET /api/v1/fleet/status endpoint"""

    def test_fleet_status_success(self, api_client, auth_headers):
        """Test successful fleet status retrieval"""
        response = api_client.get('/api/v1/fleet/status', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'version' in data or 'status' in data

    def test_fleet_status_unauthorized(self, api_client):
        """Test fleet status without authentication"""
        response = api_client.get('/api/v1/fleet/status')
        assert response.status_code == 401


@pytest.mark.integration
class TestFleetHosts:
    """Test GET /api/v1/fleet/hosts endpoints"""

    def test_list_hosts_success(self, api_client, auth_headers):
        """Test successful host list retrieval"""
        response = api_client.get('/api/v1/fleet/hosts', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'hosts' in data or 'total' in data

    def test_list_hosts_unauthorized(self, api_client):
        """Test host list without authentication"""
        response = api_client.get('/api/v1/fleet/hosts')
        assert response.status_code == 401

    def test_get_host_by_id(self, api_client, auth_headers):
        """Test retrieval of single host"""
        response = api_client.get('/api/v1/fleet/hosts/1', headers=auth_headers)
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestFleetQueries:
    """Test GET /api/v1/fleet/queries endpoints"""

    def test_list_queries_success(self, api_client, auth_headers):
        """Test successful query list retrieval"""
        response = api_client.get('/api/v1/fleet/queries', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'queries' in data or 'total' in data

    def test_list_queries_unauthorized(self, api_client):
        """Test query list without authentication"""
        response = api_client.get('/api/v1/fleet/queries')
        assert response.status_code == 401


@pytest.mark.integration
class TestFleetQueriesRun:
    """Test POST /api/v1/fleet/queries/run endpoint (license-gated)"""

    def test_run_query_with_auth(self, api_client, auth_headers):
        """Test run query with authentication"""
        payload = {'query': 'SELECT * FROM system_info;', 'host_ids': [1]}
        response = api_client.post('/api/v1/fleet/queries/run', headers=auth_headers, json=payload)
        assert response.status_code in [200, 403]

    def test_run_query_unauthorized(self, api_client):
        """Test run query without authentication"""
        payload = {'query': 'SELECT * FROM system_info;'}
        response = api_client.post('/api/v1/fleet/queries/run', json=payload)
        assert response.status_code == 401

    def test_run_query_missing_query_parameter(self, api_client, auth_headers):
        """Test run query without query parameter"""
        response = api_client.post('/api/v1/fleet/queries/run', headers=auth_headers, json={'host_ids': [1]})
        assert response.status_code in [400, 403]


@pytest.mark.integration
class TestFleetPolicies:
    """Test GET /api/v1/fleet/policies endpoint"""

    def test_list_policies_success(self, api_client, auth_headers):
        """Test successful policies list retrieval"""
        response = api_client.get('/api/v1/fleet/policies', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'policies' in data or 'total' in data

    def test_list_policies_unauthorized(self, api_client):
        """Test policies list without authentication"""
        response = api_client.get('/api/v1/fleet/policies')
        assert response.status_code == 401
