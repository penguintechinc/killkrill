"""
Httpx-based integration tests for dashboard endpoints.

Tests cover:
- GET /api/v1/dashboard/overview
- GET /api/v1/dashboard/services
- GET /api/v1/dashboard/services/{name}
- GET /api/v1/dashboard/metrics
- GET /api/v1/dashboard/activity

All tests use httpx client via conftest fixtures (no Flask imports).
Compatible with Quart async patterns via pytest-asyncio.
"""

import httpx
import pytest


@pytest.mark.integration
class TestDashboardOverview:
    """Tests for GET /api/v1/dashboard/overview endpoint."""

    def test_overview_success(self, client: httpx.Client):
        """Test successful overview retrieval."""
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "correlation_id" in data

    def test_overview_structure(self, client: httpx.Client):
        """Test overview response structure."""
        response = client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200

        overview = response.json()["data"]
        assert "total_services" in overview
        assert "healthy_services" in overview
        assert "degraded_services" in overview
        assert "total_sensors" in overview
        assert "uptime_percentage" in overview
        assert "avg_response_time_ms" in overview


@pytest.mark.integration
class TestDashboardServices:
    """Tests for GET /api/v1/dashboard/services endpoint."""

    def test_services_list_success(self, client: httpx.Client):
        """Test successful services list retrieval."""
        response = client.get("/api/v1/dashboard/services")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "count" in data
        assert len(data["data"]) > 0

    def test_services_structure(self, client: httpx.Client):
        """Test services list response structure."""
        response = client.get("/api/v1/dashboard/services")
        assert response.status_code == 200

        services = response.json()["data"]
        for service in services:
            assert "name" in service
            assert "status" in service
            assert "type" in service
            assert "version" in service
            assert "uptime_percentage" in service
            assert "response_time_ms" in service
            assert "last_check" in service

    def test_services_contains_expected(self, client: httpx.Client):
        """Test services list includes expected services."""
        response = client.get("/api/v1/dashboard/services")
        assert response.status_code == 200

        service_names = [svc["name"] for svc in response.json()["data"]]
        assert "api" in service_names


@pytest.mark.integration
class TestDashboardServiceDetails:
    """Tests for GET /api/v1/dashboard/services/{name} endpoint."""

    def test_service_details_success(self, client: httpx.Client):
        """Test successful service details retrieval."""
        response = client.get("/api/v1/dashboard/services/api")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["name"] == "api"

    def test_service_details_structure(self, client: httpx.Client):
        """Test service details has complete information."""
        response = client.get("/api/v1/dashboard/services/api")
        assert response.status_code == 200

        service = response.json()["data"]
        assert "name" in service
        assert "status" in service
        assert "type" in service
        assert "version" in service
        assert "cpu_usage_percent" in service
        assert "memory_usage_percent" in service
        assert "error_rate_percent" in service
        assert "throughput_rps" in service
        assert "dependencies" in service
        assert isinstance(service["dependencies"], list)

    def test_service_not_found(self, client: httpx.Client):
        """Test service details with non-existent service."""
        response = client.get("/api/v1/dashboard/services/nonexistent-service-xyz")
        assert response.status_code == 404

    def test_multiple_services(self, client: httpx.Client):
        """Test service details for multiple services."""
        services = ["api", "log-worker", "metrics-worker"]
        for service_name in services:
            response = client.get(f"/api/v1/dashboard/services/{service_name}")
            if response.status_code == 200:
                assert response.json()["data"]["name"] == service_name


@pytest.mark.integration
class TestDashboardMetrics:
    """Tests for GET /api/v1/dashboard/metrics endpoint."""

    def test_metrics_success(self, client: httpx.Client):
        """Test successful metrics retrieval."""
        response = client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_metrics_structure(self, client: httpx.Client):
        """Test metrics response has correct structure."""
        response = client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200

        metrics = response.json()["data"]
        assert "cpu_usage" in metrics
        assert "memory_usage" in metrics
        assert "network" in metrics
        assert "error_metrics" in metrics
        assert "storage" in metrics

    def test_metrics_cpu_usage(self, client: httpx.Client):
        """Test CPU usage metrics."""
        response = client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200

        cpu = response.json()["data"]["cpu_usage"]
        assert "current" in cpu
        assert "average_24h" in cpu
        assert "peak_24h" in cpu

    def test_metrics_memory_usage(self, client: httpx.Client):
        """Test memory usage metrics."""
        response = client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200

        memory = response.json()["data"]["memory_usage"]
        assert "current" in memory
        assert "average_24h" in memory
        assert "peak_24h" in memory

    def test_metrics_network(self, client: httpx.Client):
        """Test network metrics."""
        response = client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200

        network = response.json()["data"]["network"]
        assert "inbound_mbps" in network
        assert "outbound_mbps" in network
        assert "total_requests_24h" in network

    def test_metrics_error_metrics(self, client: httpx.Client):
        """Test error metrics."""
        response = client.get("/api/v1/dashboard/metrics")
        assert response.status_code == 200

        errors = response.json()["data"]["error_metrics"]
        assert "error_count_24h" in errors
        assert "error_rate_percent" in errors
        assert "timeout_count_24h" in errors


@pytest.mark.integration
class TestDashboardActivity:
    """Tests for GET /api/v1/dashboard/activity endpoint."""

    def test_activity_success(self, client: httpx.Client):
        """Test successful activity log retrieval."""
        response = client.get("/api/v1/dashboard/activity")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "count" in data
        assert isinstance(data["data"], list)

    def test_activity_default_limit(self, client: httpx.Client):
        """Test activity log with default limit."""
        response = client.get("/api/v1/dashboard/activity")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == len(data["data"])

    def test_activity_custom_limit(self, client: httpx.Client):
        """Test activity log with custom limit."""
        response = client.get("/api/v1/dashboard/activity?limit=10")
        assert response.status_code == 200

        assert response.json()["count"] >= 0

    def test_activity_entry_structure(self, client: httpx.Client):
        """Test activity entry has correct structure."""
        response = client.get("/api/v1/dashboard/activity")
        assert response.status_code == 200

        activities = response.json()["data"]
        if activities:
            activity = activities[0]
            assert "timestamp" in activity
            assert "event_type" in activity
            assert "service" in activity
            assert "severity" in activity
            assert "message" in activity
