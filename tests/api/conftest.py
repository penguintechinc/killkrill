"""Flask API test fixtures - uses httpx to call running API."""

import os
import pytest
import httpx

# API base URL from environment or default
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')


@pytest.fixture
def api_base_url() -> str:
    """Base URL for API requests."""
    return API_BASE_URL


@pytest.fixture
def api_client():
    """Httpx client for API requests."""
    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
async def async_api_client():
    """Async httpx client for API requests."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
def auth_token(api_client) -> str:
    """Get auth token by logging in with test credentials."""
    response = api_client.post('/api/v1/auth/login', json={
        'email': os.getenv('TEST_USER_EMAIL', 'admin@killkrill.local'),
        'password': os.getenv('TEST_USER_PASSWORD', 'admin123')
    })
    if response.status_code == 200:
        return response.json().get('access_token', '')
    return ''


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Authenticated headers."""
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json',
    }


@pytest.fixture
def json_headers() -> dict:
    """JSON content-type headers."""
    return {'Content-Type': 'application/json'}


@pytest.fixture
def invalid_auth_headers() -> dict:
    """Invalid auth headers for testing failures."""
    return {
        'Authorization': 'Bearer invalid_token_12345',
        'Content-Type': 'application/json',
    }


@pytest.fixture
def admin_headers(api_client) -> dict:
    """Admin auth headers."""
    response = api_client.post('/api/v1/auth/login', json={
        'email': os.getenv('TEST_ADMIN_EMAIL', 'admin@killkrill.local'),
        'password': os.getenv('TEST_ADMIN_PASSWORD', 'admin123')
    })
    token = response.json().get('access_token', '') if response.status_code == 200 else ''
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
