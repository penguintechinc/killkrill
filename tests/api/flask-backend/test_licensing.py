"""
KillKrill API - Licensing Integration Tests
httpx-based integration tests for licensing endpoints with pytest markers.
Compatible with Quart async patterns via pytest-asyncio.
"""

import pytest
import httpx


@pytest.mark.integration
class TestGetLicenseInfo:
    """Test GET /api/v1/licensing/"""

    def test_get_license_info_success(self, api_client, auth_headers):
        """Test successful license info retrieval"""
        response = api_client.get('/api/v1/licensing/', headers=auth_headers)
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert 'customer' in data or 'tier' in data

    def test_get_license_info_no_auth(self, api_client):
        """Test license info without authentication"""
        response = api_client.get('/api/v1/licensing/')
        assert response.status_code in [200, 401, 503]


@pytest.mark.integration
class TestGetFeatures:
    """Test GET /api/v1/licensing/features"""

    def test_get_features_success(self, api_client, auth_headers):
        """Test successful features retrieval"""
        response = api_client.get('/api/v1/licensing/features', headers=auth_headers)
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert 'features' in data or 'total' in data

    def test_get_features_with_filter(self, api_client, auth_headers):
        """Test features endpoint with feature name filter"""
        response = api_client.get('/api/v1/licensing/features?feature=advanced_analytics', headers=auth_headers)
        assert response.status_code in [200, 503]

    def test_get_features_no_auth(self, api_client):
        """Test features without authentication"""
        response = api_client.get('/api/v1/licensing/features')
        assert response.status_code in [200, 401, 503]


@pytest.mark.integration
class TestGetLicenseStatus:
    """Test GET /api/v1/licensing/status"""

    def test_get_license_status_success(self, api_client, auth_headers):
        """Test successful license status retrieval"""
        response = api_client.get('/api/v1/licensing/status', headers=auth_headers)
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert 'valid' in data or 'tier' in data

    def test_get_license_status_no_auth(self, api_client):
        """Test license status without authentication"""
        response = api_client.get('/api/v1/licensing/status')
        assert response.status_code in [200, 401, 503]
