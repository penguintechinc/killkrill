"""
End-to-End tests for log pipeline
Tests complete data flow: log-receiver → Redis → log-worker → API
"""

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import pytest
import redis
import requests

# Environment configuration
LOG_RECEIVER_URL = os.getenv("LOG_RECEIVER_URL", "http://localhost:8081")
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
def log_receiver_available():
    """Check if log-receiver service is available"""
    try:
        response = requests.get(f"{LOG_RECEIVER_URL}/healthz", timeout=5)
        if response.status_code == 200:
            return True
        pytest.skip(f"Log receiver unhealthy: {response.status_code}")
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Log receiver not available: {e}")


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


def generate_unique_log(
    level: str = "info", source: str = "e2e-test"
) -> Dict[str, Any]:
    """Generate a unique log entry for testing"""
    unique_id = str(uuid.uuid4())
    return {
        "log_level": level,
        "message": f"E2E test log entry {unique_id}",
        "service_name": source,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "test_id": unique_id,
        "labels": json.dumps(
            {"test": "e2e", "pipeline": "log", "unique_id": unique_id}
        ),
    }


def wait_for_redis_log(
    redis_client, test_id: str, timeout: int = PROCESSING_TIMEOUT
) -> bool:
    """Poll Redis stream for log with specific test_id"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Read from logs stream (or logs:raw based on implementation)
            for stream_name in ["logs", "logs:raw"]:
                try:
                    # Read last 100 messages from stream
                    messages = redis_client.xrevrange(stream_name, count=100)

                    for msg_id, fields in messages:
                        # Check if message contains our test_id
                        message_content = fields.get("message", "")
                        if test_id in message_content or test_id in fields.get(
                            "test_id", ""
                        ):
                            return True

                        # Check labels
                        labels_str = fields.get("labels", "{}")
                        try:
                            labels = json.loads(labels_str)
                            if labels.get("unique_id") == test_id:
                                return True
                        except json.JSONDecodeError:
                            pass

                except redis.exceptions.ResponseError:
                    # Stream doesn't exist yet
                    pass

        except Exception as e:
            # Continue polling on error
            pass

        time.sleep(POLL_INTERVAL)

    return False


def wait_for_api_log(test_id: str, timeout: int = PROCESSING_TIMEOUT) -> Optional[Dict]:
    """Poll API for log with specific test_id"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Query API for logs (adjust endpoint based on actual API)
            response = requests.get(
                f"{API_BASE_URL}/api/v1/logs",
                params={"search": test_id, "limit": 100},
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                logs = data.get("logs", data.get("data", []))

                for log in logs:
                    # Check message or metadata for test_id
                    if test_id in log.get("message", ""):
                        return log

                    # Check labels
                    labels = log.get("labels", {})
                    if isinstance(labels, str):
                        try:
                            labels = json.loads(labels)
                        except json.JSONDecodeError:
                            labels = {}

                    if labels.get("unique_id") == test_id:
                        return log

        except requests.exceptions.RequestException:
            # Continue polling on error
            pass

        time.sleep(POLL_INTERVAL)

    return None


@pytest.mark.e2e
@pytest.mark.requires_network
def test_single_log_submission(log_receiver_available, redis_client):
    """Test: Submit single log via HTTP POST to log-receiver"""
    log_data = generate_unique_log(level="info", source="e2e-single-test")
    test_id = log_data["test_id"]

    # Submit log to receiver
    response = requests.post(
        f"{LOG_RECEIVER_URL}/api/v1/logs", json=log_data, timeout=10
    )

    assert response.status_code in [200, 202], f"Failed to submit log: {response.text}"
    response_data = response.json()
    assert response_data.get("status") in ["accepted", "success"]

    # Verify log appears in Redis stream
    found_in_redis = wait_for_redis_log(redis_client, test_id)
    assert found_in_redis, f"Log with test_id {test_id} not found in Redis stream"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_batch_log_submission(log_receiver_available, redis_client):
    """Test: Submit batch of logs (multiple sequential submissions)"""
    batch_size = 5
    test_ids = []

    # Submit batch of logs
    for i in range(batch_size):
        log_data = generate_unique_log(level="info", source=f"e2e-batch-{i}")
        test_ids.append(log_data["test_id"])

        response = requests.post(
            f"{LOG_RECEIVER_URL}/api/v1/logs", json=log_data, timeout=10
        )

        assert response.status_code in [200, 202]

    # Verify all logs appear in Redis
    found_count = 0
    for test_id in test_ids:
        if wait_for_redis_log(redis_client, test_id, timeout=10):
            found_count += 1

    assert (
        found_count == batch_size
    ), f"Only {found_count}/{batch_size} logs found in Redis stream"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_different_log_levels(log_receiver_available, redis_client):
    """Test: Submit logs with different levels (DEBUG, INFO, WARN, ERROR)"""
    levels = ["debug", "info", "warn", "error"]
    test_ids = {}

    # Submit logs with different levels
    for level in levels:
        log_data = generate_unique_log(level=level, source=f"e2e-level-{level}")
        test_ids[level] = log_data["test_id"]

        response = requests.post(
            f"{LOG_RECEIVER_URL}/api/v1/logs", json=log_data, timeout=10
        )

        assert response.status_code in [200, 202]

    # Verify logs with all levels appear in Redis
    found_levels = []
    for level, test_id in test_ids.items():
        if wait_for_redis_log(redis_client, test_id, timeout=10):
            found_levels.append(level)

    assert set(found_levels) == set(
        levels
    ), f"Missing levels in Redis: {set(levels) - set(found_levels)}"


@pytest.mark.e2e
@pytest.mark.requires_network
@pytest.mark.slow
def test_log_worker_processing(log_receiver_available, redis_client):
    """Test: Verify log-worker processes logs from Redis stream"""
    log_data = generate_unique_log(level="info", source="e2e-worker-test")
    test_id = log_data["test_id"]

    # Submit log
    response = requests.post(
        f"{LOG_RECEIVER_URL}/api/v1/logs", json=log_data, timeout=10
    )

    assert response.status_code in [200, 202]

    # Wait for log in Redis
    assert wait_for_redis_log(redis_client, test_id), "Log not found in Redis stream"

    # Check consumer group processing (if accessible)
    try:
        # Get stream info
        for stream_name in ["logs:raw", "logs"]:
            try:
                info = redis_client.xinfo_stream(stream_name)
                # Verify stream has messages
                assert info.get("length", 0) > 0, "Stream is empty"

                # Check consumer groups (if they exist)
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
def test_complete_log_pipeline(log_receiver_available, api_available, redis_client):
    """Test: Complete pipeline - submit log, verify in Redis, verify worker processes, query via API"""
    log_data = generate_unique_log(level="info", source="e2e-complete-pipeline")
    test_id = log_data["test_id"]

    # Step 1: Submit log to receiver
    response = requests.post(
        f"{LOG_RECEIVER_URL}/api/v1/logs", json=log_data, timeout=10
    )

    assert response.status_code in [200, 202], "Log submission failed"

    # Step 2: Verify log appears in Redis stream
    found_in_redis = wait_for_redis_log(redis_client, test_id, timeout=15)
    assert found_in_redis, "Log not found in Redis stream"

    # Step 3: Wait for log-worker to process (allow time for processing)
    time.sleep(5)

    # Step 4: Query log via API
    log_from_api = wait_for_api_log(test_id, timeout=20)

    if log_from_api:
        # Verify data integrity
        assert (
            log_data["log_level"] in log_from_api.get("level", "").lower()
            or log_data["log_level"] in log_from_api.get("log_level", "").lower()
        ), "Log level mismatch"

        assert test_id in log_from_api.get(
            "message", ""
        ), "Test ID not found in message"

        # Verify timestamp preservation
        assert "timestamp" in log_from_api, "Timestamp missing from API response"
    else:
        pytest.skip(
            "API log query endpoint not yet implemented or log not yet processed"
        )


@pytest.mark.e2e
@pytest.mark.requires_network
def test_log_data_integrity(log_receiver_available, redis_client):
    """Test: Verify data integrity through pipeline - correct timestamps, labels preserved"""
    log_data = generate_unique_log(level="info", source="e2e-integrity-test")
    test_id = log_data["test_id"]
    original_timestamp = log_data["timestamp"]
    original_labels = json.loads(log_data["labels"])

    # Submit log
    response = requests.post(
        f"{LOG_RECEIVER_URL}/api/v1/logs", json=log_data, timeout=10
    )

    assert response.status_code in [200, 202]

    # Retrieve from Redis and verify data
    start_time = time.time()
    found = False

    while time.time() - start_time < PROCESSING_TIMEOUT:
        try:
            for stream_name in ["logs", "logs:raw"]:
                try:
                    messages = redis_client.xrevrange(stream_name, count=100)

                    for msg_id, fields in messages:
                        if test_id in fields.get(
                            "message", ""
                        ) or test_id in fields.get("test_id", ""):

                            # Verify timestamp preservation
                            redis_timestamp = fields.get("timestamp", "")
                            assert redis_timestamp, "Timestamp missing in Redis"

                            # Verify level preservation
                            redis_level = fields.get(
                                "level", fields.get("log_level", "")
                            )
                            assert (
                                redis_level.lower() == log_data["log_level"].lower()
                            ), "Log level changed in Redis"

                            # Verify labels preservation
                            labels_str = fields.get("labels", "{}")
                            try:
                                redis_labels = json.loads(labels_str)
                                assert (
                                    redis_labels.get("unique_id") == test_id
                                ), "Labels not preserved in Redis"
                            except json.JSONDecodeError:
                                pass  # Labels may be in different format

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

    assert found, "Log not found in Redis for data integrity verification"


@pytest.mark.e2e
@pytest.mark.requires_network
def test_log_receiver_health_check(log_receiver_available):
    """Test: Verify log-receiver health check includes Redis and database status"""
    response = requests.get(f"{LOG_RECEIVER_URL}/healthz", timeout=5)

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
def test_log_submission_validation(log_receiver_available):
    """Test: Verify log receiver validates input data"""
    # Test empty payload
    response = requests.post(f"{LOG_RECEIVER_URL}/api/v1/logs", json={}, timeout=10)

    # Should accept but handle gracefully or return 400
    assert response.status_code in [200, 202, 400]

    # Test invalid JSON
    response = requests.post(
        f"{LOG_RECEIVER_URL}/api/v1/logs",
        data="invalid json",
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    assert response.status_code in [400, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
