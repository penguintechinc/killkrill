"""
Pytest configuration for log processor unit tests.

Sets up mocks for external dependencies before importing the module.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))


# ============================================================================
# Mock External Dependencies Before Import
# ============================================================================

# Mock redis
sys.modules["redis"] = MagicMock()

# Mock elasticsearch
sys.modules["elasticsearch"] = MagicMock()
sys.modules["elasticsearch.helpers"] = MagicMock()

# Mock structlog
sys.modules["structlog"] = MagicMock()
sys.modules["structlog.stdlib"] = MagicMock()
sys.modules["structlog.processors"] = MagicMock()

# Mock prometheus_client
sys.modules["prometheus_client"] = MagicMock()

# Mock shared modules
sys.modules["shared"] = MagicMock()
sys.modules["shared.licensing"] = MagicMock()
sys.modules["shared.licensing.client"] = MagicMock()
sys.modules["shared.config"] = MagicMock()
sys.modules["shared.config.settings"] = MagicMock()


@pytest.fixture(scope="session", autouse=True)
def setup_module_mocks():
    """Set up module-level mocks before any imports."""
    # Create mock configuration
    mock_config = MagicMock()
    mock_config.redis_url = "redis://localhost:6379"
    mock_config.elasticsearch_hosts = ["localhost:9200"]
    mock_config.prometheus_gateway = "http://localhost:9091"
    mock_config.license_key = "PENG-TEST-TEST-TEST-TEST-ABCD"
    mock_config.product_name = "killkrill-test"
    mock_config.processor_workers = 2
    mock_batch_size = 500
    mock_config.max_batch_size = mock_batch_size
    mock_config.processing_timeout = 30
    mock_config.elasticsearch_index_prefix = "killkrill"

    # Patch get_config to return mock config
    with patch("shared.config.settings.get_config", return_value=mock_config):
        yield


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MagicMock()


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch client."""
    return MagicMock()


@pytest.fixture
def mock_license_client():
    """Mock license client."""
    client = MagicMock()
    client.validate.return_value = {"valid": True, "tier": "professional"}
    client.keepalive.return_value = True
    return client
