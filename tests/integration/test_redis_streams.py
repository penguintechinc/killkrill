"""
Integration tests for Redis streams operations.

Tests cover:
- Stream publishing (XADD) - single and batch
- Stream consuming (XREAD) - blocking and non-blocking
- Consumer groups (XGROUP CREATE, XREADGROUP)
- Message acknowledgment (XACK)
- Pending message handling (XPENDING, XCLAIM)
- Stream info and length (XINFO, XLEN)

Requires: pytest>=7.4, pytest-asyncio>=0.23, redis>=5.0
"""

import asyncio
import os
import time
import uuid
from typing import Any, AsyncGenerator, Generator, Optional

import pytest
import redis
import redis.asyncio as aioredis

# Test markers
pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_network,
]


# Check if Redis is available
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_AVAILABLE = os.getenv("TEST_REDIS_ENABLED", "false").lower() == "true"


@pytest.fixture(scope="session")
def redis_available() -> bool:
    """Check if Redis server is available."""
    if not REDIS_AVAILABLE:
        pytest.skip("Redis integration tests disabled. Set TEST_REDIS_ENABLED=true")
    return True


@pytest.fixture
def redis_client(redis_available: bool) -> Generator[redis.Redis, None, None]:
    """Sync Redis client fixture."""
    client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )

    try:
        # Test connection
        client.ping()
        yield client
    finally:
        client.close()


@pytest.fixture
async def async_redis_client(
    redis_available: bool,
) -> AsyncGenerator[aioredis.Redis, None]:
    """Async Redis client fixture."""
    client = aioredis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )

    try:
        # Test connection
        await client.ping()
        yield client
    finally:
        await client.close()


@pytest.fixture
def test_stream_name() -> Generator[str, None, None]:
    """Generate unique stream name for each test."""
    stream_name = f"test_stream_{uuid.uuid4().hex[:8]}"
    yield stream_name
    # Cleanup handled by redis_client fixture teardown


@pytest.fixture
def cleanup_stream(redis_client: redis.Redis, test_stream_name: str):
    """Cleanup stream after test."""
    yield
    try:
        redis_client.delete(test_stream_name)
    except Exception:
        pass


@pytest.fixture
def test_consumer_group() -> str:
    """Generate unique consumer group name."""
    return f"test_group_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_consumer_name() -> str:
    """Generate unique consumer name."""
    return f"test_consumer_{uuid.uuid4().hex[:8]}"


# Sync tests
class TestSyncStreamsBasics:
    """Test basic Redis streams operations with sync client."""

    def test_stream_single_publish(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test publishing single message to stream."""
        # Publish message
        msg_id = redis_client.xadd(
            test_stream_name,
            {"field1": "value1", "field2": "value2"},
        )

        assert msg_id is not None
        assert "-" in msg_id  # Format: timestamp-sequence

        # Verify stream length
        length = redis_client.xlen(test_stream_name)
        assert length == 1

    def test_stream_batch_publish(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test batch publishing to stream."""
        batch_size = 100

        # Publish batch using pipeline
        pipe = redis_client.pipeline()
        for i in range(batch_size):
            pipe.xadd(
                test_stream_name,
                {"index": str(i), "timestamp": str(time.time())},
            )
        results = pipe.execute()

        assert len(results) == batch_size
        assert all(r is not None for r in results)

        # Verify stream length
        length = redis_client.xlen(test_stream_name)
        assert length == batch_size

    def test_stream_non_blocking_read(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test non-blocking stream read (XREAD)."""
        # Publish test messages
        msg_ids = []
        for i in range(5):
            msg_id = redis_client.xadd(
                test_stream_name,
                {"message": f"test_{i}"},
            )
            msg_ids.append(msg_id)

        # Read from beginning
        messages = redis_client.xread(
            {test_stream_name: "0"},
            count=3,
        )

        assert len(messages) == 1  # One stream
        assert messages[0][0] == test_stream_name
        assert len(messages[0][1]) == 3  # 3 messages

        # Verify message structure
        msg_id, fields = messages[0][1][0]
        assert msg_id in msg_ids
        assert "message" in fields

    def test_stream_blocking_read(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test blocking stream read with timeout."""
        # Read with timeout (should return empty)
        messages = redis_client.xread(
            {test_stream_name: "$"},  # Read new messages only
            block=100,  # 100ms timeout
        )

        assert messages == [] or messages is None

    def test_stream_maxlen_trimming(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test stream trimming with MAXLEN."""
        max_length = 10

        # Publish messages with maxlen constraint
        for i in range(20):
            redis_client.xadd(
                test_stream_name,
                {"index": str(i)},
                maxlen=max_length,
                approximate=False,
            )

        # Verify stream length doesn't exceed maxlen
        length = redis_client.xlen(test_stream_name)
        assert length == max_length

    def test_stream_info(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test XINFO STREAM command."""
        # Publish some messages
        for i in range(5):
            redis_client.xadd(test_stream_name, {"msg": str(i)})

        # Get stream info
        info = redis_client.xinfo_stream(test_stream_name)

        assert info["length"] == 5
        assert "first-entry" in info
        assert "last-entry" in info


class TestSyncConsumerGroups:
    """Test Redis consumer group operations with sync client."""

    def test_consumer_group_create(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
        cleanup_stream,
    ):
        """Test creating consumer group."""
        # Create stream with initial message
        redis_client.xadd(test_stream_name, {"init": "true"})

        # Create consumer group
        result = redis_client.xgroup_create(
            test_stream_name,
            test_consumer_group,
            id="0",
            mkstream=True,
        )

        assert result is True

        # Verify group exists
        groups = redis_client.xinfo_groups(test_stream_name)
        assert len(groups) == 1
        assert groups[0]["name"] == test_consumer_group

    def test_consumer_group_read(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
        test_consumer_name: str,
        cleanup_stream,
    ):
        """Test reading from consumer group."""
        # Setup: create stream and group
        redis_client.xadd(test_stream_name, {"msg": "test1"})
        redis_client.xadd(test_stream_name, {"msg": "test2"})
        redis_client.xgroup_create(
            test_stream_name,
            test_consumer_group,
            id="0",
        )

        # Read messages as consumer
        messages = redis_client.xreadgroup(
            test_consumer_group,
            test_consumer_name,
            {test_stream_name: ">"},
            count=2,
        )

        assert len(messages) == 1
        assert len(messages[0][1]) == 2

        # Verify consumer exists
        consumers = redis_client.xinfo_consumers(
            test_stream_name,
            test_consumer_group,
        )
        assert len(consumers) == 1
        assert consumers[0]["name"] == test_consumer_name

    def test_message_acknowledgment(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
        test_consumer_name: str,
        cleanup_stream,
    ):
        """Test message acknowledgment (XACK)."""
        # Setup
        msg_id = redis_client.xadd(test_stream_name, {"msg": "test"})
        redis_client.xgroup_create(test_stream_name, test_consumer_group, id="0")

        # Read message
        messages = redis_client.xreadgroup(
            test_consumer_group,
            test_consumer_name,
            {test_stream_name: ">"},
        )

        assert len(messages[0][1]) == 1
        read_msg_id = messages[0][1][0][0]

        # Acknowledge message
        ack_count = redis_client.xack(
            test_stream_name,
            test_consumer_group,
            read_msg_id,
        )

        assert ack_count == 1

    def test_pending_messages(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
        test_consumer_name: str,
        cleanup_stream,
    ):
        """Test pending message handling (XPENDING)."""
        # Setup: publish and read without ack
        msg_id = redis_client.xadd(test_stream_name, {"msg": "test"})
        redis_client.xgroup_create(test_stream_name, test_consumer_group, id="0")

        redis_client.xreadgroup(
            test_consumer_group,
            test_consumer_name,
            {test_stream_name: ">"},
        )

        # Check pending messages
        pending = redis_client.xpending(test_stream_name, test_consumer_group)

        assert pending["pending"] == 1
        assert pending["min"] == msg_id
        assert pending["max"] == msg_id

    def test_claim_pending_messages(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
        cleanup_stream,
    ):
        """Test claiming pending messages (XCLAIM)."""
        consumer1 = f"consumer1_{uuid.uuid4().hex[:8]}"
        consumer2 = f"consumer2_{uuid.uuid4().hex[:8]}"

        # Setup: consumer1 reads but doesn't ack
        msg_id = redis_client.xadd(test_stream_name, {"msg": "test"})
        redis_client.xgroup_create(test_stream_name, test_consumer_group, id="0")

        redis_client.xreadgroup(
            test_consumer_group,
            consumer1,
            {test_stream_name: ">"},
        )

        # Wait a bit to simulate stale message
        time.sleep(0.1)

        # Consumer2 claims the message
        claimed = redis_client.xclaim(
            test_stream_name,
            test_consumer_group,
            consumer2,
            min_idle_time=50,  # 50ms
            message_ids=[msg_id],
        )

        assert len(claimed) == 1
        assert claimed[0][0] == msg_id


# Async tests
class TestAsyncStreamsBasics:
    """Test basic Redis streams operations with async client."""

    @pytest.mark.asyncio
    async def test_async_stream_publish(
        self,
        async_redis_client: aioredis.Redis,
        test_stream_name: str,
    ):
        """Test async stream publishing."""
        try:
            msg_id = await async_redis_client.xadd(
                test_stream_name,
                {"field": "value"},
            )

            assert msg_id is not None

            length = await async_redis_client.xlen(test_stream_name)
            assert length == 1
        finally:
            await async_redis_client.delete(test_stream_name)

    @pytest.mark.asyncio
    async def test_async_stream_read(
        self,
        async_redis_client: aioredis.Redis,
        test_stream_name: str,
    ):
        """Test async stream reading."""
        try:
            # Publish test message
            await async_redis_client.xadd(
                test_stream_name,
                {"test": "data"},
            )

            # Read message
            messages = await async_redis_client.xread(
                {test_stream_name: "0"},
            )

            assert len(messages) == 1
            assert len(messages[0][1]) == 1
        finally:
            await async_redis_client.delete(test_stream_name)

    @pytest.mark.asyncio
    async def test_async_consumer_group(
        self,
        async_redis_client: aioredis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
        test_consumer_name: str,
    ):
        """Test async consumer group operations."""
        try:
            # Setup
            await async_redis_client.xadd(test_stream_name, {"msg": "test"})
            await async_redis_client.xgroup_create(
                test_stream_name,
                test_consumer_group,
                id="0",
            )

            # Read as consumer
            messages = await async_redis_client.xreadgroup(
                test_consumer_group,
                test_consumer_name,
                {test_stream_name: ">"},
            )

            assert len(messages) == 1
            assert len(messages[0][1]) == 1

            # Acknowledge
            msg_id = messages[0][1][0][0]
            ack_count = await async_redis_client.xack(
                test_stream_name,
                test_consumer_group,
                msg_id,
            )

            assert ack_count == 1
        finally:
            await async_redis_client.delete(test_stream_name)


class TestErrorHandling:
    """Test error handling for Redis stream operations."""

    def test_read_nonexistent_stream(
        self,
        redis_client: redis.Redis,
    ):
        """Test reading from non-existent stream."""
        messages = redis_client.xread(
            {"nonexistent_stream": "0"},
            count=1,
        )

        # Should return empty, not error
        assert messages == []

    def test_duplicate_consumer_group(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
        cleanup_stream,
    ):
        """Test creating duplicate consumer group."""
        redis_client.xadd(test_stream_name, {"init": "true"})
        redis_client.xgroup_create(test_stream_name, test_consumer_group, id="0")

        # Try to create again - should raise error
        with pytest.raises(redis.ResponseError):
            redis_client.xgroup_create(
                test_stream_name,
                test_consumer_group,
                id="0",
            )

    @pytest.mark.asyncio
    async def test_async_connection_error(self):
        """Test handling async connection errors."""
        # Invalid URL
        client = aioredis.from_url(
            "redis://invalid-host:6379",
            socket_timeout=1,
            socket_connect_timeout=1,
        )

        with pytest.raises((redis.ConnectionError, asyncio.TimeoutError)):
            await client.ping()


class TestHighThroughput:
    """Test high-throughput scenarios."""

    def test_high_volume_publish(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test publishing high volume of messages."""
        message_count = 1000
        batch_size = 100

        for batch in range(0, message_count, batch_size):
            pipe = redis_client.pipeline()
            for i in range(batch_size):
                pipe.xadd(
                    test_stream_name,
                    {"index": str(batch + i), "data": f"payload_{i}"},
                )
            pipe.execute()

        length = redis_client.xlen(test_stream_name)
        assert length == message_count

    @pytest.mark.asyncio
    async def test_concurrent_consumers(
        self,
        async_redis_client: aioredis.Redis,
        test_stream_name: str,
        test_consumer_group: str,
    ):
        """Test multiple concurrent consumers."""
        try:
            # Setup: publish messages
            message_count = 50
            for i in range(message_count):
                await async_redis_client.xadd(
                    test_stream_name,
                    {"index": str(i)},
                )

            await async_redis_client.xgroup_create(
                test_stream_name,
                test_consumer_group,
                id="0",
            )

            # Concurrent consumers
            async def consume(consumer_name: str) -> int:
                messages = await async_redis_client.xreadgroup(
                    test_consumer_group,
                    consumer_name,
                    {test_stream_name: ">"},
                    count=10,
                )
                return len(messages[0][1]) if messages else 0

            # Run 5 consumers concurrently
            consumer_names = [f"consumer_{i}" for i in range(5)]
            results = await asyncio.gather(*[consume(name) for name in consumer_names])

            # All messages should be distributed among consumers
            total_consumed = sum(results)
            assert total_consumed == message_count
        finally:
            await async_redis_client.delete(test_stream_name)


class TestStreamMetadata:
    """Test stream metadata and info commands."""

    def test_xinfo_stream_full(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test XINFO STREAM with full details."""
        # Publish messages
        for i in range(10):
            redis_client.xadd(test_stream_name, {"index": str(i)})

        info = redis_client.xinfo_stream(test_stream_name, full=True)

        assert "length" in info
        assert "entries" in info
        assert info["length"] == 10

    def test_xinfo_groups(
        self,
        redis_client: redis.Redis,
        test_stream_name: str,
        cleanup_stream,
    ):
        """Test XINFO GROUPS command."""
        redis_client.xadd(test_stream_name, {"init": "true"})

        # Create multiple groups
        groups = ["group1", "group2", "group3"]
        for group in groups:
            redis_client.xgroup_create(test_stream_name, group, id="0")

        info = redis_client.xinfo_groups(test_stream_name)

        assert len(info) == 3
        group_names = [g["name"] for g in info]
        assert all(g in group_names for g in groups)
