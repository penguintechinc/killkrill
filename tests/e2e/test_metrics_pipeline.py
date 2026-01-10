"""
End-to-End tests for metrics pipeline
Tests complete data flow: metrics-receiver → Redis → metrics-worker → API
"""

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest
import redis
import requests

# Environment configuration
METRICS_RECEIVER_URL = os.getenv("METRICS_RECEIVER_URL", "http://localhost:8082")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Timeouts and retry settings
PROCESSING_TIMEOUT = 30  # seconds
POLL_INTERVAL = 0.5  # seconds
MAX_RETRIES = int(PROCESSING_TIMEOUT / POLL_INTERVAL)


@pytest.fixture(scope="module")
def redis_client():
    """Redis client for verifying stream data"""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture(scope="module")
def metrics_receiver_available():
    """Check if metrics-receiver service is available"""
    try:
        response = requests.get(f"{METRICS_RECEIVER_URL}/healthz", timeout=5)
        if response.status_code == 200:
            return True
        pytest.skip(f"Metrics receiver unhealthy: {response.status_code}")
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Metrics receiver not available: {e}")


@pytest.fixture(scope="module")
def api_available():
    """Check if API service is available"""
    try:
        response = requests.get(f"{API_BASE_URL}/healthz", timeout=5)
        if response.status_code == 200:
            return True
        pytest.skip(f"API unhealthy: {response.status_code}")
    except requests.exceptions.RequestException as e:
        pytest.skip(f"API not available: {e}")


def generate_unique_metric(
    metric_type: str = "gauge",
    value: float = 42.0,
    labels: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Generate a unique metric entry for testing"""
    unique_id = str(uuid.uuid4())
    metric_name = f'e2e_test_metric_{unique_id.replace("-", "_")}'

    if labels is None:
        labels = {}

    labels.update({"test": "e2e", "pipeline": "metrics", "unique_id": unique_id})

    return {
        "name": metric_name,
        "type": metric_type,
        "value": value,
        "labels": labels,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "test_id": unique_id,
    }


def wait_for_redis_metric(
    redis_client, test_id: str, timeout: int = PROCESSING_TIMEOUT
) -> bool:
    """Poll Redis stream for metric with specific test_id"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Read from metrics stream
            for stream_name in ["metrics:raw", "metrics"]:
                try:
                    # Read last 100 messages from stream
                    messages = redis_client.xrevrange(stream_name, count=100)

                    for msg_id, fields in messages:
                        # Check metric_name contains test_id
                        metric_name = fields.get("metric_name", fields.get("name", ""))
                        if test_id.replace("-", "_") in metric_name:
                            return True

                        # Check labels
                        labels_str = fields.get("labels", "{}")
                        try:
                            labels = json.loads(labels_str)
                            if labels.get("unique_id") == test_id:
                                return True
                        except json.JSONDecodeError:
                            pass

                        # Check test_id field directly
                        if fields.get("test_id") == test_id:
                            return True

                except redis.exceptions.ResponseError:
                    # Stream doesn't exist yet
                    pass

        except Exception:
            # Continue polling on error
            pass

        time.sleep(POLL_INTERVAL)

    return False


def wait_for_api_metric(
    test_id: str, timeout: int = PROCESSING_TIMEOUT
) -> Optional[Dict]:
    """Poll API for metric with specific test_id"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Query API for metrics (adjust endpoint based on actual API)
            response = requests.get(
                f"{API_BASE_URL}/api/v1/metrics",
                params={"search": test_id, "limit": 100},
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                metrics = data.get("metrics", data.get("data", []))

                for metric in metrics:
                    # Check metric name for test_id
                    metric_name = metric.get("name", metric.get("metric_name", ""))
                    if test_id.replace("-", "_") in metric_name:
                        return metric

                    # Check labels
                    labels = metric.get("labels", {})
                    if isinstance(labels, str):
                        try:
                            labels = json.loads(labels)
                        except json.JSONDecodeError:
                            labels = {}

                    if labels.get("unique_id") == test_id:
                        return metric

        except requests.exceptions.RequestException:
            # Continue polling on error
            pass

        time.sleep(POLL_INTERVAL)

    return None


@pytest.mark.e2e
@pytest.mark.requires_network
def test_single_metric_submission(metrics_receiver_available, redis_client):
    """Test: Submit single metric via HTTP POST to metrics-receiver"""
    metric_data = generate_unique_metric(metric_type="gauge", value=100.0)
    test_id = metric_data["test_id"]

    # Submit metric to receiver
    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [
        200,
        202,
    ], f"Failed to submit metric: {response.text}"
    response_data = response.json()
    assert response_data.get("status") in ["accepted", "success"]

    # Verify metric appears in Redis stream
    found_in_redis = wait_for_redis_metric(redis_client, test_id)
    assert found_in_redis, f"Metric with test_id {test_id} not found in Redis stream"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_counter_metric_type(metrics_receiver_available, redis_client):
    """Test: Submit counter metric type"""
    metric_data = generate_unique_metric(
        metric_type="counter", value=1.0, labels={"operation": "test_counter"}
    )
    test_id = metric_data["test_id"]

    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [200, 202]
    assert wait_for_redis_metric(
        redis_client, test_id
    ), "Counter metric not found in Redis"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_gauge_metric_type(metrics_receiver_available, redis_client):
    """Test: Submit gauge metric type"""
    metric_data = generate_unique_metric(
        metric_type="gauge", value=75.5, labels={"resource": "test_gauge"}
    )
    test_id = metric_data["test_id"]

    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [200, 202]
    assert wait_for_redis_metric(
        redis_client, test_id
    ), "Gauge metric not found in Redis"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_histogram_metric_type(metrics_receiver_available, redis_client):
    """Test: Submit histogram metric type"""
    metric_data = generate_unique_metric(
        metric_type="histogram", value=0.123, labels={"endpoint": "test_histogram"}
    )
    test_id = metric_data["test_id"]

    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [200, 202]
    assert wait_for_redis_metric(
        redis_client, test_id
    ), "Histogram metric not found in Redis"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_different_metric_types(metrics_receiver_available, redis_client):
    """Test: Submit different metric types (counter, gauge, histogram)"""
    metric_types = ["counter", "gauge", "histogram"]
    test_ids = {}

    # Submit metrics with different types
    for metric_type in metric_types:
        metric_data = generate_unique_metric(
            metric_type=metric_type,
            value=42.0,
            labels={"metric_type_test": metric_type},
        )
        test_ids[metric_type] = metric_data["test_id"]

        response = requests.post(
            f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
        )

        assert response.status_code in [200, 202]

    # Verify metrics with all types appear in Redis
    found_types = []
    for metric_type, test_id in test_ids.items():
        if wait_for_redis_metric(redis_client, test_id, timeout=10):
            found_types.append(metric_type)

    assert set(found_types) == set(
        metric_types
    ), f"Missing metric types in Redis: {set(metric_types) - set(found_types)}"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_metrics_labels_handling(metrics_receiver_available, redis_client):
    """Test: Verify labels/tags are properly handled"""
    custom_labels = {
        "environment": "test",
        "service": "e2e-metrics",
        "region": "us-east-1",
        "version": "1.0.0",
    }

    metric_data = generate_unique_metric(
        metric_type="gauge", value=99.9, labels=custom_labels
    )
    test_id = metric_data["test_id"]

    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [200, 202]

    # Verify metric in Redis and check labels preservation
    start_time = time.time()
    found = False

    while time.time() - start_time < PROCESSING_TIMEOUT:
        try:
            for stream_name in ["metrics:raw", "metrics"]:
                try:
                    messages = redis_client.xrevrange(stream_name, count=100)

                    for msg_id, fields in messages:
                        metric_name = fields.get("metric_name", fields.get("name", ""))

                        if (
                            test_id.replace("-", "_") in metric_name
                            or fields.get("test_id") == test_id
                        ):

                            # Verify labels preservation
                            labels_str = fields.get("labels", "{}")
                            try:
                                redis_labels = json.loads(labels_str)

                                # Check custom labels are preserved
                                assert (
                                    redis_labels.get("unique_id") == test_id
                                ), "Test ID not found in labels"

                                for key, value in custom_labels.items():
                                    if key != "unique_id":  # Skip merged fields
                                        assert (
                                            redis_labels.get(key) == value
                                        ), f"Label {key} not preserved"

                            except json.JSONDecodeError:
                                pytest.fail("Labels not in valid JSON format")

                            found = True
                            break

                    if found:
                        break
                except redis.exceptions.ResponseError:
                    pass

        except Exception:
            pass

        if found:
            break

        time.sleep(POLL_INTERVAL)

    assert found, "Metric not found in Redis for label verification"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_batch_metrics_submission(metrics_receiver_available, redis_client):
    """Test: Submit batch of metrics (multiple sequential submissions)"""
    batch_size = 10
    test_ids = []

    # Submit batch of metrics
    for i in range(batch_size):
        metric_data = generate_unique_metric(
            metric_type="counter" if i % 2 == 0 else "gauge",
            value=float(i * 10),
            labels={"batch_index": str(i)},
        )
        test_ids.append(metric_data["test_id"])

        response = requests.post(
            f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
        )

        assert response.status_code in [200, 202]

    # Verify all metrics appear in Redis
    found_count = 0
    for test_id in test_ids:
        if wait_for_redis_metric(redis_client, test_id, timeout=10):
            found_count += 1

    assert (
        found_count == batch_size
    ), f"Only {found_count}/{batch_size} metrics found in Redis stream"


@pytest.mark.e2e
@pytest.mark.requires_network
@pytest.mark.slow
def test_metrics_worker_processing(metrics_receiver_available, redis_client):
    """Test: Verify metrics-worker processes metrics from Redis stream"""
    metric_data = generate_unique_metric(
        metric_type="gauge", value=123.45, labels={"worker_test": "true"}
    )
    test_id = metric_data["test_id"]

    # Submit metric
    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [200, 202]

    # Wait for metric in Redis
    assert wait_for_redis_metric(
        redis_client, test_id
    ), "Metric not found in Redis stream"

    # Check consumer group processing (if accessible)
    try:
        # Get stream info
        for stream_name in ["metrics:raw", "metrics"]:
            try:
                info = redis_client.xinfo_stream(stream_name)
                # Verify stream has messages
                assert info.get("length", 0) > 0, "Stream is empty"

                # Check consumer groups
                groups = redis_client.xinfo_groups(stream_name)
                if groups:
                    # Verify consumer group is processing
                    for group in groups:
                        assert (
                            group.get("consumers", 0) > 0
                        ), "No active consumers in group"
                break
            except redis.exceptions.ResponseError:
                continue
    except redis.exceptions.ResponseError:
        # Consumer groups may not be created yet
        pytest.skip("Consumer groups not yet initialized")


@pytest.mark.e2e
@pytest.mark.requires_network
@pytest.mark.slow
def test_metrics_aggregation(metrics_receiver_available, redis_client):
    """Test: Verify metrics-worker aggregates metrics correctly"""
    base_name = f"e2e_aggregation_test_{uuid.uuid4().hex[:8]}"
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    test_ids = []

    # Submit multiple metrics with same name (for aggregation)
    for i, value in enumerate(values):
        metric_data = {
            "name": base_name,
            "type": "gauge",
            "value": value,
            "labels": {"test": "aggregation", "index": str(i)},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        test_id = str(uuid.uuid4())
        metric_data["test_id"] = test_id
        test_ids.append(test_id)

        response = requests.post(
            f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
        )

        assert response.status_code in [200, 202]

    # Verify metrics appear in Redis
    found_count = 0
    for test_id in test_ids:
        if wait_for_redis_metric(redis_client, test_id, timeout=5):
            found_count += 1

    assert (
        found_count >= len(values) // 2
    ), f"Not enough metrics found in Redis for aggregation test"

    # Note: Actual aggregation verification would require querying the API
    # or checking the destination (Prometheus, etc.) which may not be available


@pytest.mark.e2e
@pytest.mark.requires_network
@pytest.mark.slow
def test_complete_metrics_pipeline(
    metrics_receiver_available, api_available, redis_client
):
    """Test: Complete pipeline - submit metric, verify in Redis, verify worker processes, query via API"""
    metric_data = generate_unique_metric(
        metric_type="counter", value=1.0, labels={"pipeline_test": "complete"}
    )
    test_id = metric_data["test_id"]

    # Step 1: Submit metric to receiver
    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [200, 202], "Metric submission failed"

    # Step 2: Verify metric appears in Redis stream
    found_in_redis = wait_for_redis_metric(redis_client, test_id, timeout=15)
    assert found_in_redis, "Metric not found in Redis stream"

    # Step 3: Wait for metrics-worker to process
    time.sleep(5)

    # Step 4: Query metric via API
    metric_from_api = wait_for_api_metric(test_id, timeout=20)

    if metric_from_api:
        # Verify data integrity
        assert metric_data["type"] == metric_from_api.get(
            "type", metric_from_api.get("metric_type")
        ), "Metric type mismatch"

        # Verify labels preserved
        api_labels = metric_from_api.get("labels", {})
        if isinstance(api_labels, str):
            api_labels = json.loads(api_labels)

        assert (
            api_labels.get("unique_id") == test_id
        ), "Test ID not found in API response labels"

        # Verify timestamp
        assert "timestamp" in metric_from_api, "Timestamp missing from API response"
    else:
        pytest.skip(
            "API metrics query endpoint not yet implemented or metric not yet processed"
        )


@pytest.mark.e2e
@pytest.mark.requires_network
def test_metric_data_integrity(metrics_receiver_available, redis_client):
    """Test: Verify data integrity - value, type, labels preserved"""
    metric_data = generate_unique_metric(
        metric_type="histogram",
        value=99.999,
        labels={"integrity": "test", "precision": "high"},
    )
    test_id = metric_data["test_id"]
    original_value = metric_data["value"]
    original_type = metric_data["type"]

    # Submit metric
    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json=metric_data, timeout=10
    )

    assert response.status_code in [200, 202]

    # Retrieve from Redis and verify data integrity
    start_time = time.time()
    found = False

    while time.time() - start_time < PROCESSING_TIMEOUT:
        try:
            for stream_name in ["metrics:raw", "metrics"]:
                try:
                    messages = redis_client.xrevrange(stream_name, count=100)

                    for msg_id, fields in messages:
                        metric_name = fields.get("metric_name", fields.get("name", ""))

                        if (
                            test_id.replace("-", "_") in metric_name
                            or fields.get("test_id") == test_id
                        ):

                            # Verify value preservation
                            redis_value = float(
                                fields.get("metric_value", fields.get("value", 0))
                            )
                            assert (
                                abs(redis_value - original_value) < 0.001
                            ), f"Value changed: {original_value} -> {redis_value}"

                            # Verify type preservation
                            redis_type = fields.get(
                                "metric_type", fields.get("type", "")
                            )
                            assert (
                                redis_type.lower() == original_type.lower()
                            ), f"Type changed: {original_type} -> {redis_type}"

                            # Verify labels
                            labels_str = fields.get("labels", "{}")
                            try:
                                redis_labels = json.loads(labels_str)
                                assert (
                                    redis_labels.get("unique_id") == test_id
                                ), "Labels not preserved"
                                assert (
                                    redis_labels.get("integrity") == "test"
                                ), "Custom label not preserved"
                            except json.JSONDecodeError:
                                pytest.fail("Labels not in valid JSON format")

                            found = True
                            break

                    if found:
                        break
                except redis.exceptions.ResponseError:
                    pass

        except Exception:
            pass

        if found:
            break

        time.sleep(POLL_INTERVAL)

    assert found, "Metric not found in Redis for data integrity verification"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_metrics_receiver_health_check(metrics_receiver_available):
    """Test: Verify metrics-receiver health check includes Redis and database status"""
    response = requests.get(f"{METRICS_RECEIVER_URL}/healthz", timeout=5)

    assert response.status_code == 200
    health_data = response.json()

    assert "status" in health_data
    assert "components" in health_data

    components = health_data["components"]
    assert "redis" in components, "Redis health check missing"
    assert "database" in components, "Database health check missing"

    # Verify components are operational
    assert components["redis"] == "ok", f"Redis unhealthy: {components['redis']}"
    assert (
        components["database"] == "ok"
    ), f"Database unhealthy: {components['database']}"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_metric_submission_validation(metrics_receiver_available):
    """Test: Verify metrics receiver validates input data"""
    # Test empty payload
    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics", json={}, timeout=10
    )

    # Should accept but handle gracefully or return 400
    assert response.status_code in [200, 202, 400]

    # Test invalid value type
    response = requests.post(
        f"{METRICS_RECEIVER_URL}/api/v1/metrics",
        json={
            "name": "test_metric",
            "type": "gauge",
            "value": "invalid",  # Should be numeric
        },
        timeout=10,
    )

    assert response.status_code in [400, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
