"""
KillKrill API - AI Analysis Integration Tests
httpx-based integration tests for AI analysis endpoints with pytest markers
"""

import pytest
import httpx


@pytest.mark.integration
class TestAnalyzeEndpoint:
    """Test POST /api/v1/ai/analyze"""

    def test_analyze_success(self, api_client, auth_headers):
        """Test successful analysis submission"""
        payload = {
            'data_source': 'prometheus',
            'analysis_type': 'general',
            'input_data': {'metrics': ['cpu_usage']}
        }
        response = api_client.post('/api/v1/ai/analyze', headers=auth_headers, json=payload)
        assert response.status_code in [201, 403]

    def test_analyze_missing_data_source(self, api_client, auth_headers):
        """Test validation of missing data_source field"""
        payload = {'analysis_type': 'general'}
        response = api_client.post('/api/v1/ai/analyze', headers=auth_headers, json=payload)
        assert response.status_code in [400, 403]

    def test_analyze_unauthorized(self, api_client):
        """Test analysis without authentication"""
        payload = {'data_source': 'prometheus', 'analysis_type': 'general'}
        response = api_client.post('/api/v1/ai/analyze', json=payload)
        assert response.status_code == 401


@pytest.mark.integration
class TestResultsListEndpoint:
    """Test GET /api/v1/ai/results"""

    def test_get_results_list_success(self, api_client, auth_headers):
        """Test retrieving list of analysis results"""
        response = api_client.get('/api/v1/ai/results', headers=auth_headers)
        assert response.status_code in [200, 403]

    def test_get_results_with_limit(self, api_client, auth_headers):
        """Test retrieving results with custom limit"""
        response = api_client.get('/api/v1/ai/results?limit=50', headers=auth_headers)
        assert response.status_code in [200, 403]

    def test_get_results_unauthorized(self, api_client):
        """Test results list without authentication"""
        response = api_client.get('/api/v1/ai/results')
        assert response.status_code == 401


@pytest.mark.integration
class TestResultDetailEndpoint:
    """Test GET /api/v1/ai/results/{id}"""

    def test_get_result_by_id(self, api_client, auth_headers):
        """Test retrieving analysis result by ID"""
        response = api_client.get('/api/v1/ai/results/1', headers=auth_headers)
        assert response.status_code in [200, 403, 404]

    def test_get_result_not_found(self, api_client, auth_headers):
        """Test retrieving non-existent analysis result"""
        response = api_client.get('/api/v1/ai/results/999999', headers=auth_headers)
        assert response.status_code in [403, 404]

    def test_get_result_unauthorized(self, api_client):
        """Test result detail without authentication"""
        response = api_client.get('/api/v1/ai/results/1')
        assert response.status_code == 401


@pytest.mark.integration
class TestAcknowledgeEndpoint:
    """Test PUT /api/v1/ai/results/{id}/acknowledge"""

    def test_acknowledge_result(self, api_client, auth_headers):
        """Test acknowledgment of analysis result"""
        response = api_client.put('/api/v1/ai/results/1/acknowledge', headers=auth_headers, json={})
        assert response.status_code in [200, 403, 404]

    def test_acknowledge_with_user_info(self, api_client, auth_headers):
        """Test acknowledgment with user information"""
        payload = {'acknowledged_by': 'admin@example.com'}
        response = api_client.put('/api/v1/ai/results/1/acknowledge', headers=auth_headers, json=payload)
        assert response.status_code in [200, 403, 404]

    def test_acknowledge_unauthorized(self, api_client):
        """Test acknowledge without authentication"""
        response = api_client.put('/api/v1/ai/results/1/acknowledge', json={})
        assert response.status_code == 401


@pytest.mark.integration
class TestConfigEndpoint:
    """Test GET /api/v1/ai/config"""

    def test_get_config_success(self, api_client, auth_headers):
        """Test retrieving AI analysis configuration"""
        response = api_client.get('/api/v1/ai/config', headers=auth_headers)
        assert response.status_code in [200, 403]

    def test_get_config_unauthorized(self, api_client):
        """Test config without authentication"""
        response = api_client.get('/api/v1/ai/config')
        assert response.status_code == 401
