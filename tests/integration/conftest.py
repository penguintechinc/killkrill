"""
KillKrill - Integration Test Fixtures

Provides test fixtures for database operations and integration tests.
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Generator

import pytest

# Optional imports - skip if not available
try:
    from pydal import DAL, Field

    PYDAL_AVAILABLE = True
except ImportError:
    PYDAL_AVAILABLE = False
    DAL = None
    Field = None


# Test markers
def pytest_configure(config):
    """Register custom pytest markers"""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line(
        "markers", "requires_db: mark test as requiring real database connection"
    )


@pytest.fixture(scope="session")
def test_db_config():
    """
    Test database configuration from environment variables.

    Defaults to SQLite for fast tests without external dependencies.
    Override with environment variables for PostgreSQL/MySQL testing.
    """
    db_type = os.getenv("TEST_DB_TYPE", "sqlite")
    db_url = os.getenv("TEST_DB_URL", "")

    # SQLite default: use temp directory
    if db_type == "sqlite" and not db_url:
        test_db_dir = "/tmp/killkrill-tests"
        os.makedirs(test_db_dir, exist_ok=True)
        db_path = os.path.join(test_db_dir, "test_killkrill.db")
        db_url = f"sqlite://{db_path}"

    return {
        "db_type": db_type,
        "db_url": db_url,
        "pool_size": int(os.getenv("TEST_DB_POOL_SIZE", "5")),
    }


@pytest.fixture(scope="function")
def pydal_db(test_db_config) -> Generator[DAL, None, None]:
    """
    Create PyDAL database instance for testing with clean state per test.

    Yields:
        DAL: PyDAL database instance with all tables defined

    Cleanup:
        - Drops all test data after each test
        - Closes database connection
    """
    if not PYDAL_AVAILABLE:
        pytest.skip("PyDAL not available")

    # Create persistent migrations folder (do not use tempfile.mkdtemp)
    migrations_folder = "/tmp/killkrill-tests/pydal-migrations"
    os.makedirs(migrations_folder, exist_ok=True)

    # Create PyDAL instance
    db = DAL(
        test_db_config["db_url"],
        folder=migrations_folder,
        pool_size=test_db_config["pool_size"],
        migrate=True,
        fake_migrate=False,
        check_reserved=[],
    )

    # Define all test tables
    _define_test_tables(db)

    yield db

    # Cleanup: truncate all tables and close connection
    try:
        for table in db.tables:
            db[table].truncate()
        db.commit()
    except Exception:
        pass  # Ignore cleanup errors
    finally:
        db.close()


def _define_test_tables(db: DAL) -> None:
    """Define all database tables for testing"""

    # Users table - use auto-incrementing id
    db.define_table(
        "users",
        Field("email", "string", length=255, unique=True),
        Field("password_hash", "string", length=255),
        Field("name", "string", length=255),
        Field("role", "string", length=32, default="viewer"),
        Field("is_active", "boolean", default=True),
        Field("fs_uniquifier", "string", length=64, unique=True),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # API Keys table - use auto-incrementing id
    db.define_table(
        "api_keys",
        Field("user_id", "reference users"),
        Field("name", "string", length=128),
        Field("key_hash", "string", length=64),
        Field("permissions", "json"),
        Field("expires_at", "datetime"),
        Field("last_used_at", "datetime"),
        Field("is_active", "boolean", default=True),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # Sensor Agents table - use auto-incrementing id
    db.define_table(
        "sensor_agents",
        Field("agent_id", "string", length=64, unique=True),
        Field("name", "string", length=128),
        Field("hostname", "string", length=255),
        Field("ip_address", "string", length=45),
        Field("api_key_hash", "string", length=64),
        Field("agent_version", "string", length=32),
        Field("is_active", "boolean", default=True),
        Field("last_heartbeat", "datetime"),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # Sensor Checks table - use auto-incrementing id
    db.define_table(
        "sensor_checks",
        Field("name", "string", length=128),
        Field("check_type", "string", length=16),
        Field("target", "string", length=255),
        Field("port", "integer"),
        Field("interval_seconds", "integer", default=60),
        Field("timeout_seconds", "integer", default=30),
        Field("is_active", "boolean", default=True),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # Sensor Results table - use auto-incrementing id
    db.define_table(
        "sensor_results",
        Field("check_id", "reference sensor_checks"),
        Field("agent_id", "reference sensor_agents"),
        Field("status", "string", length=16),
        Field("response_time_ms", "integer"),
        Field("status_code", "integer"),
        Field("error_message", "string", length=1000),
        Field("ssl_valid", "boolean"),
        Field("ssl_expiry", "datetime"),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # Audit Log table - use auto-incrementing id
    db.define_table(
        "audit_log",
        Field("user_id", "reference users"),
        Field("audit_action", "string", length=128),
        Field("resource_type", "string", length=64),
        Field("resource_id", "string", length=64),
        Field("details", "json"),
        Field("ip_address", "string", length=45),
        Field("user_agent", "string", length=512),
        Field("created_at", "datetime"),
        migrate=True,
    )

    db.commit()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "email": "test@example.com",
        "password_hash": "hashed_password_value",
        "name": "Test User",
        "role": "admin",
        "is_active": True,
        "fs_uniquifier": "unique-123",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


@pytest.fixture
def sample_api_key_data(pydal_db, sample_user_data):
    """
    Sample API key data for testing.
    Note: Requires user to be inserted first for foreign key.
    """
    # Insert user and get auto-generated ID
    user_id = pydal_db.users.insert(**sample_user_data)
    pydal_db.commit()

    return {
        "user_id": user_id,
        "name": "Test API Key",
        "key_hash": "hashed_key_value",
        "permissions": ["read", "write"],
        "expires_at": datetime.utcnow() + timedelta(days=30),
        "is_active": True,
        "created_at": datetime.utcnow(),
    }


@pytest.fixture
def sample_sensor_agent_data():
    """Sample sensor agent data for testing"""
    return {
        "agent_id": "sensor-001",
        "name": "Test Sensor Agent",
        "hostname": "test-host-01.example.com",
        "ip_address": "192.168.1.100",
        "api_key_hash": "hashed_api_key",
        "agent_version": "1.0.0",
        "is_active": True,
        "last_heartbeat": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


@pytest.fixture
def db_connection_retry_config():
    """Configuration for database connection retry logic testing"""
    return {
        "max_retries": 3,
        "retry_delay": 0.1,  # 100ms for fast tests
        "timeout": 5,
    }
