"""Pytest fixtures for Flask backend API integration tests."""

import os
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock

import httpx
import pytest

# API base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")

# Note: pytest_plugins configured in root tests/conftest.py


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """API base URL."""
    return API_BASE_URL


@pytest.fixture
def client() -> Generator[httpx.Client, None, None]:
    """Httpx client for sync API calls."""
    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as c:
        yield c


@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Httpx async client for async API calls (Quart compatible)."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as c:
        yield c


@pytest.fixture
def mock_db():
    """Mock database for unit tests."""
    db = MagicMock()
    db.users = MagicMock()
    db.api_keys = MagicMock()
    db.roles = MagicMock()
    db.sensor_agents = MagicMock()
    db.sensor_checks = MagicMock()
    db.sensor_results = MagicMock()
    db.audit_log = MagicMock()
    return db


@pytest.fixture
def test_user_data() -> dict:
    """Test user data."""
    return {
        "email": "test@killkrill.local",
        "password": "TestPass123!",
        "name": "Test User",
    }


@pytest.fixture
def admin_user_data() -> dict:
    """Admin user data."""
    return {
        "email": os.getenv("TEST_ADMIN_EMAIL", "admin@killkrill.local"),
        "password": os.getenv("TEST_ADMIN_PASSWORD", "Admin123!"),
    }


@pytest.fixture
def auth_token(client, admin_user_data) -> str:
    """Get auth token from login."""
    try:
        response = client.post("/api/v1/auth/login", json=admin_user_data)
        if response.status_code == 200:
            return response.json().get("access_token", "mock_token")
    except httpx.ConnectError:
        pass
    return "mock_token_for_offline_tests"


@pytest.fixture
def auth_headers(auth_token) -> dict:
    """Authenticated request headers."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture
def json_headers() -> dict:
    """JSON headers without auth."""
    return {"Content-Type": "application/json"}


@pytest.fixture
def api_client(client) -> httpx.Client:
    """Alias for client fixture (common naming convention)."""
    return client


@pytest.fixture
def sample_sensor_agent() -> dict:
    """Sample sensor agent data."""
    return {
        "name": "test-agent-01",
        "hostname": "sensor01.killkrill.local",
        "ip_address": "192.168.1.100",
        "version": "1.0.0",
    }


@pytest.fixture
def sample_sensor_check() -> dict:
    """Sample sensor check data."""
    return {
        "name": "HTTP Check - Google",
        "check_type": "http",
        "target": "https://google.com",
        "interval_seconds": 60,
        "timeout_seconds": 30,
    }


@pytest.fixture
def sample_check_result() -> dict:
    """Sample check result data."""
    return {
        "check_id": "check-001",
        "status": "up",
        "response_time_ms": 150,
        "status_code": 200,
    }
