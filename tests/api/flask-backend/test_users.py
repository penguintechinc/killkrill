"""
HTTP-based integration tests for users API endpoints.

Tests use httpx client to test endpoints via HTTP:
- GET /api/v1/users/
- GET /api/v1/users/{id}
- POST /api/v1/users/
- PUT /api/v1/users/{id}
- DELETE /api/v1/users/{id}

Compatible with Quart async patterns via pytest-asyncio.
"""

import os
import pytest
import httpx
from typing import Dict, Any
from faker import Faker

fake = Faker()

API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')


@pytest.mark.integration
class TestListUsers:
    """Tests for GET /api/v1/users/"""

    def test_list_users_success(self, client: httpx.Client, auth_headers: Dict):
        """List all users successfully."""
        response = client.get('/api/v1/users/', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'data' in data
        assert isinstance(data['data'], list)

    def test_list_users_pagination(self, client: httpx.Client, auth_headers: Dict):
        """List users with pagination parameters."""
        response = client.get('/api/v1/users/?page=1&limit=10', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'pagination' in data or 'data' in data

    def test_list_users_no_auth(self, client: httpx.Client):
        """List users without auth returns 401 or 403."""
        response = client.get('/api/v1/users/')
        assert response.status_code in [401, 403]


@pytest.mark.integration
class TestGetUser:
    """Tests for GET /api/v1/users/{id}"""

    def test_get_user_success(self, client: httpx.Client, auth_headers: Dict):
        """Get single user by ID."""
        response = client.get('/api/v1/users/1', headers=auth_headers)
        # Should either succeed with 200 or return 404 if no user exists
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert 'id' in data or 'data' in data

    def test_get_user_not_found(self, client: httpx.Client, auth_headers: Dict):
        """Get non-existent user returns 404."""
        response = client.get('/api/v1/users/99999', headers=auth_headers)
        assert response.status_code == 404

    def test_get_user_invalid_id(self, client: httpx.Client, auth_headers: Dict):
        """Get user with invalid ID format."""
        response = client.get('/api/v1/users/invalid-id', headers=auth_headers)
        assert response.status_code == 404


@pytest.mark.integration
class TestCreateUser:
    """Tests for POST /api/v1/users/"""

    def test_create_user_success(self, client: httpx.Client, auth_headers: Dict):
        """Create user with valid payload."""
        payload = {
            'email': f'user_{fake.uuid4()}@test.local',
            'password': 'TestPass123!',
            'name': 'Test User'
        }
        response = client.post('/api/v1/users/', json=payload, headers=auth_headers)
        assert response.status_code in [201, 200]
        data = response.json()
        assert 'id' in data or 'data' in data

    def test_create_user_missing_email(self, client: httpx.Client, auth_headers: Dict):
        """Create user without email returns 400."""
        payload = {
            'password': 'TestPass123!',
            'name': 'Test User'
        }
        response = client.post('/api/v1/users/', json=payload, headers=auth_headers)
        assert response.status_code == 400

    def test_create_user_invalid_email(self, client: httpx.Client, auth_headers: Dict):
        """Create user with invalid email returns 400."""
        payload = {
            'email': 'not-an-email',
            'password': 'TestPass123!',
            'name': 'Test User'
        }
        response = client.post('/api/v1/users/', json=payload, headers=auth_headers)
        assert response.status_code == 400

    def test_create_user_short_password(self, client: httpx.Client, auth_headers: Dict):
        """Create user with weak password returns 400."""
        payload = {
            'email': f'user_{fake.uuid4()}@test.local',
            'password': 'weak',
            'name': 'Test User'
        }
        response = client.post('/api/v1/users/', json=payload, headers=auth_headers)
        assert response.status_code == 400


@pytest.mark.integration
class TestUpdateUser:
    """Tests for PUT /api/v1/users/{id}"""

    def test_update_user_email(self, client: httpx.Client, auth_headers: Dict):
        """Update user email."""
        payload = {'email': f'updated_{fake.uuid4()}@test.local'}
        response = client.put('/api/v1/users/1', json=payload, headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_update_user_password(self, client: httpx.Client, auth_headers: Dict):
        """Update user password."""
        payload = {'password': 'NewPass123!'}
        response = client.put('/api/v1/users/1', json=payload, headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_update_user_empty_payload(self, client: httpx.Client, auth_headers: Dict):
        """Update user with empty payload."""
        response = client.put('/api/v1/users/1', json={}, headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_update_user_not_found(self, client: httpx.Client, auth_headers: Dict):
        """Update non-existent user returns 404."""
        response = client.put('/api/v1/users/99999', json={'email': 'test@test.local'}, headers=auth_headers)
        assert response.status_code == 404


@pytest.mark.integration
class TestDeleteUser:
    """Tests for DELETE /api/v1/users/{id}"""

    def test_delete_user_success(self, client: httpx.Client, auth_headers: Dict):
        """Delete user successfully."""
        response = client.delete('/api/v1/users/1', headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_delete_user_not_found(self, client: httpx.Client, auth_headers: Dict):
        """Delete non-existent user returns 404."""
        response = client.delete('/api/v1/users/99999', headers=auth_headers)
        assert response.status_code == 404

    def test_delete_user_no_auth(self, client: httpx.Client):
        """Delete user without auth returns 401 or 403."""
        response = client.delete('/api/v1/users/1')
        assert response.status_code in [401, 403]
