"""Global pytest fixtures for killkrill API tests."""

import os
import sys
from datetime import datetime, timedelta
from typing import Generator

import pytest
from faker import Faker

# Configure pytest-asyncio for async test support
pytest_plugins = ("pytest_asyncio",)

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

fake = Faker()


@pytest.fixture
def api_url() -> str:
    """Get API base URL from environment or use default."""
    return os.getenv("API_URL", "http://localhost:5000")


@pytest.fixture
def auth_token() -> str:
    """Generate a test JWT token."""
    # In production, use actual JWT generation with proper secrets
    return f"test_token_{fake.uuid4()}"


@pytest.fixture
def api_headers(auth_token: str) -> dict:
    """Standard API headers with auth token."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def test_user_data() -> dict:
    """Generate test user data."""
    return {
        "username": fake.user_name(),
        "email": fake.email(),
        "password": fake.password(length=12, special_chars=True),
    }


@pytest.fixture
def test_api_key() -> str:
    """Generate a test API key."""
    return f"sk_test_{fake.uuid4()}"


@pytest.fixture
def test_license_key() -> str:
    """Generate a test license key."""
    return f"PENG-{fake.bothify(text='????')}-{fake.bothify(text='????')}-{fake.bothify(text='????')}-{fake.bothify(text='????')}-ABCD"


@pytest.fixture
def mock_db_config() -> dict:
    """Mock database configuration for testing."""
    return {
        "host": os.getenv("TEST_DB_HOST", "localhost"),
        "port": int(os.getenv("TEST_DB_PORT", "5432")),
        "database": os.getenv("TEST_DB_NAME", "killkrill_test"),
        "user": os.getenv("TEST_DB_USER", "test_user"),
        "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
    }


@pytest.fixture
def test_timestamps() -> dict:
    """Generate test timestamps."""
    now = datetime.utcnow()
    return {
        "now": now,
        "tomorrow": now + timedelta(days=1),
        "yesterday": now - timedelta(days=1),
        "next_week": now + timedelta(weeks=1),
        "next_month": now + timedelta(days=30),
    }


@pytest.fixture(scope="session")
def test_data_dir() -> str:
    """Get test data directory path."""
    test_dir = os.path.dirname(__file__)
    return os.path.join(test_dir, "data")


@pytest.fixture
def random_id() -> Generator[str, None, None]:
    """Generate random IDs for testing."""

    def _generate():
        return f"{fake.uuid4()}"

    return _generate
