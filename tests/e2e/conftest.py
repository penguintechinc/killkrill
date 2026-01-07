"""E2E test fixtures for killkrill user workflows."""

import os
import sys
from typing import Generator, Dict, Any
from uuid import uuid4

import httpx
import pytest
from faker import Faker

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

fake = Faker()

# API base URL from environment or default
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')


@pytest.fixture(scope='session')
def api_base_url() -> str:
    """Base URL for API requests."""
    return API_BASE_URL


@pytest.fixture
def api_client() -> Generator[httpx.Client, None, None]:
    """Synchronous httpx client for E2E tests."""
    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
        # Check if API is available
        try:
            response = client.get('/healthz')
            if response.status_code not in [200, 404]:
                pytest.skip(f"API not available at {API_BASE_URL}")
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip(f"Cannot connect to API at {API_BASE_URL}")
        yield client


@pytest.fixture
async def async_api_client() -> Generator[httpx.AsyncClient, None, None]:
    """Async httpx client for E2E tests."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        # Check if API is available
        try:
            response = await client.get('/healthz')
            if response.status_code not in [200, 404]:
                pytest.skip(f"API not available at {API_BASE_URL}")
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip(f"Cannot connect to API at {API_BASE_URL}")
        yield client


@pytest.fixture
def admin_credentials() -> Dict[str, str]:
    """Admin credentials for setup operations."""
    return {
        'email': os.getenv('TEST_ADMIN_EMAIL', 'admin@killkrill.local'),
        'password': os.getenv('TEST_ADMIN_PASSWORD', 'admin123'),
    }


@pytest.fixture
def admin_token(api_client, admin_credentials) -> str:
    """Get admin JWT token."""
    try:
        response = api_client.post('/api/v1/auth/login', json=admin_credentials)
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token', '')
    except Exception:
        pass
    pytest.skip("Admin authentication not available")


@pytest.fixture
def admin_headers(admin_token: str) -> Dict[str, str]:
    """Admin authenticated headers."""
    return {
        'Authorization': f'Bearer {admin_token}',
        'Content-Type': 'application/json',
    }


@pytest.fixture
def test_user_data() -> Dict[str, str]:
    """Generate unique test user data for each test."""
    unique_id = uuid4().hex[:8]
    return {
        'email': f'testuser{unique_id}@killkrill.test',
        'password': 'TestPass123!',
        'name': f'Test User {unique_id}',
    }


@pytest.fixture
def test_user(api_client, test_user_data) -> Generator[Dict[str, Any], None, None]:
    """Create test user and cleanup after test."""
    user_data = None
    user_id = None

    # Create user
    try:
        response = api_client.post('/api/v1/auth/register', json=test_user_data)
        if response.status_code in [200, 201]:
            user_data = response.json()
            user_id = user_data.get('id') or user_data.get('user', {}).get('id')
    except Exception:
        pass

    yield test_user_data

    # Cleanup: delete user if created
    if user_id:
        try:
            # Get admin token for deletion
            admin_creds = {
                'email': os.getenv('TEST_ADMIN_EMAIL', 'admin@killkrill.local'),
                'password': os.getenv('TEST_ADMIN_PASSWORD', 'admin123'),
            }
            admin_response = api_client.post('/api/v1/auth/login', json=admin_creds)
            if admin_response.status_code == 200:
                admin_token = admin_response.json().get('access_token')
                api_client.delete(
                    f'/api/v1/users/{user_id}',
                    headers={'Authorization': f'Bearer {admin_token}'}
                )
        except Exception:
            pass  # Cleanup is best-effort


@pytest.fixture
def viewer_user_data() -> Dict[str, str]:
    """Generate viewer role user data."""
    unique_id = uuid4().hex[:8]
    return {
        'email': f'viewer{unique_id}@killkrill.test',
        'password': 'ViewerPass123!',
        'name': f'Viewer User {unique_id}',
        'role': 'viewer',
    }


@pytest.fixture
def maintainer_user_data() -> Dict[str, str]:
    """Generate maintainer role user data."""
    unique_id = uuid4().hex[:8]
    return {
        'email': f'maintainer{unique_id}@killkrill.test',
        'password': 'MaintainerPass123!',
        'name': f'Maintainer User {unique_id}',
        'role': 'maintainer',
    }


@pytest.fixture
def mock_email_verification() -> Dict[str, str]:
    """Mock email verification token."""
    return {
        'token': f'verify_{uuid4().hex}',
        'expires_in': 3600,
    }


@pytest.fixture
def mock_password_reset_token() -> str:
    """Mock password reset token."""
    return f'reset_{uuid4().hex}'


@pytest.fixture
def json_headers() -> Dict[str, str]:
    """JSON content-type headers."""
    return {'Content-Type': 'application/json'}


@pytest.fixture
def random_api_key_name() -> str:
    """Generate random API key name."""
    return f'test-key-{uuid4().hex[:8]}'
