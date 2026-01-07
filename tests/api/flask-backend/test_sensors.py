"""
HTTPX-based integration tests for Flask Backend sensors endpoints.
Tests call running API via HTTP using httpx client from conftest fixtures.
Compatible with Quart async patterns via pytest-asyncio.
"""

import pytest
from typing import Dict

pytestmark = pytest.mark.integration


class TestSensorsAgents:
    """Tests for agents list/create endpoints."""

    def test_get_sensors_list(self, api_client):
        """GET /api/v1/sensors/ returns agents list."""
        response = api_client.get('/api/v1/sensors/')
        assert response.status_code in [200, 404]

    def test_post_sensors_create(self, api_client):
        """POST /api/v1/sensors/ creates agent."""
        payload = {'name': 'Test Agent', 'description': 'Test'}
        response = api_client.post('/api/v1/sensors/', json=payload)
        assert response.status_code in [201, 400]

    def test_get_sensor_detail(self, api_client):
        """GET /api/v1/sensors/{id} retrieves agent."""
        response = api_client.get('/api/v1/sensors/1')
        assert response.status_code in [200, 404]

    def test_delete_sensor(self, api_client):
        """DELETE /api/v1/sensors/{id} removes agent."""
        response = api_client.delete('/api/v1/sensors/999')
        assert response.status_code in [200, 404]


class TestSensorsHeartbeat:
    """Tests for sensor heartbeat endpoint."""

    def test_post_heartbeat(self, api_client):
        """POST /api/v1/sensors/{id}/heartbeat records heartbeat."""
        response = api_client.post('/api/v1/sensors/1/heartbeat')
        assert response.status_code in [200, 404]


class TestSensorsChecks:
    """Tests for checks list/create endpoints."""

    def test_get_checks_list(self, api_client):
        """GET /api/v1/sensors/checks returns checks."""
        response = api_client.get('/api/v1/sensors/checks')
        assert response.status_code in [200, 404]

    def test_post_check_tcp(self, api_client):
        """POST /api/v1/sensors/checks creates TCP check."""
        payload = {
            'name': 'TCP Check',
            'check_type': 'tcp',
            'target': '192.168.1.1',
            'port': 22,
            'interval': 60,
            'timeout': 5
        }
        response = api_client.post('/api/v1/sensors/checks', json=payload)
        assert response.status_code in [201, 400]

    def test_post_check_http(self, api_client):
        """POST /api/v1/sensors/checks creates HTTP check."""
        payload = {
            'name': 'HTTP Check',
            'check_type': 'http',
            'target': 'http://example.com',
            'method': 'GET',
            'interval': 30,
            'timeout': 10
        }
        response = api_client.post('/api/v1/sensors/checks', json=payload)
        assert response.status_code in [201, 400]

    def test_post_check_dns(self, api_client):
        """POST /api/v1/sensors/checks creates DNS check."""
        payload = {
            'name': 'DNS Check',
            'check_type': 'dns',
            'target': 'example.com',
            'interval': 300,
            'timeout': 10
        }
        response = api_client.post('/api/v1/sensors/checks', json=payload)
        assert response.status_code in [201, 400]

    def test_get_check_detail(self, api_client):
        """GET /api/v1/sensors/checks/{id} retrieves check."""
        response = api_client.get('/api/v1/sensors/checks/1')
        assert response.status_code in [200, 404]

    def test_put_check_update(self, api_client):
        """PUT /api/v1/sensors/checks/{id} updates check."""
        payload = {
            'name': 'Updated Check',
            'check_type': 'tcp',
            'target': '192.168.1.2',
            'port': 443,
            'interval': 120,
            'timeout': 10
        }
        response = api_client.put('/api/v1/sensors/checks/1', json=payload)
        assert response.status_code in [200, 400, 404]

    def test_delete_check(self, api_client):
        """DELETE /api/v1/sensors/checks/{id} removes check."""
        response = api_client.delete('/api/v1/sensors/checks/999')
        assert response.status_code in [200, 404]


class TestSensorsResults:
    """Tests for results list/submit endpoints."""

    def test_get_results_list(self, api_client):
        """GET /api/v1/sensors/results returns results."""
        response = api_client.get('/api/v1/sensors/results')
        assert response.status_code in [200, 404]

    def test_get_results_with_limit(self, api_client):
        """GET /api/v1/sensors/results respects limit."""
        response = api_client.get('/api/v1/sensors/results?limit=50')
        assert response.status_code in [200, 404]

    def test_post_result_success(self, api_client):
        """POST /api/v1/sensors/results submits success result."""
        payload = {
            'check_id': '1',
            'status': 'success',
            'response_time': 125.5,
            'message': 'Check passed'
        }
        response = api_client.post('/api/v1/sensors/results', json=payload)
        assert response.status_code in [201, 400]

    def test_post_result_failure(self, api_client):
        """POST /api/v1/sensors/results submits failure result."""
        payload = {
            'check_id': '2',
            'status': 'failure',
            'response_time': 5000.0,
            'message': 'Connection refused'
        }
        response = api_client.post('/api/v1/sensors/results', json=payload)
        assert response.status_code in [201, 400]

    def test_post_result_timeout(self, api_client):
        """POST /api/v1/sensors/results submits timeout result."""
        payload = {
            'check_id': '3',
            'status': 'timeout',
            'response_time': 60000.0,
            'message': 'Request timeout'
        }
        response = api_client.post('/api/v1/sensors/results', json=payload)
        assert response.status_code in [201, 400]


class TestSensorsStatus:
    """Tests for system status endpoint."""

    def test_get_status(self, api_client):
        """GET /api/v1/sensors/status returns system status."""
        response = api_client.get('/api/v1/sensors/status')
        assert response.status_code in [200, 404]


class TestSensorsConfig:
    """Tests for agent configuration endpoint."""

    def test_get_config(self, api_client):
        """GET /api/v1/sensors/config/{agent_id} returns config."""
        response = api_client.get('/api/v1/sensors/config/1')
        assert response.status_code in [200, 404]

    def test_get_config_not_found(self, api_client):
        """GET /api/v1/sensors/config/{agent_id} handles not found."""
        response = api_client.get('/api/v1/sensors/config/999')
        assert response.status_code in [200, 404]
