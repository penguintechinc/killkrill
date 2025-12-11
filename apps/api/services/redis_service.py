"""
KillKrill API - Redis Service
Async Redis client management
"""

from typing import Optional
from contextvars import ContextVar

import redis.asyncio as redis
from quart import Quart
import structlog

from config import get_config

logger = structlog.get_logger(__name__)

# Context variable for Redis client
_redis_context: ContextVar[Optional[redis.Redis]] = ContextVar('redis', default=None)

# Global Redis client
_redis_client: Optional[redis.Redis] = None


async def init_redis(app: Quart) -> None:
    """Initialize Redis connection"""
    global _redis_client

    config = app.killkrill_config

    try:
        _redis_client = redis.from_url(
            config.REDIS_URL,
            encoding='utf-8',
            decode_responses=True,
            max_connections=config.REDIS_MAX_CONNECTIONS,
        )

        # Test connection
        await _redis_client.ping()

        app.redis = _redis_client
        logger.info("redis_initialized", url=config.REDIS_URL.split('@')[-1])

    except Exception as e:
        logger.error("redis_init_failed", error=str(e))
        _redis_client = None


async def close_redis(app: Quart) -> None:
    """Close Redis connection"""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_closed")


async def get_redis() -> Optional[redis.Redis]:
    """Get Redis client"""
    return _redis_client


class RedisCache:
    """
    Redis caching utilities
    """

    def __init__(self, prefix: str = 'killkrill'):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Generate prefixed key"""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[str]:
        """Get cached value"""
        client = await get_redis()
        if not client:
            return None
        return await client.get(self._key(key))

    async def set(self, key: str, value: str, ttl: int = 300) -> bool:
        """Set cached value with TTL"""
        client = await get_redis()
        if not client:
            return False
        await client.setex(self._key(key), ttl, value)
        return True

    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        client = await get_redis()
        if not client:
            return False
        await client.delete(self._key(key))
        return True

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        client = await get_redis()
        if not client:
            return False
        return await client.exists(self._key(key)) > 0

    async def incr(self, key: str, ttl: int = None) -> int:
        """Increment counter"""
        client = await get_redis()
        if not client:
            return 0
        value = await client.incr(self._key(key))
        if ttl:
            await client.expire(self._key(key), ttl)
        return value

    async def get_json(self, key: str) -> Optional[dict]:
        """Get cached JSON value"""
        import json
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: dict, ttl: int = 300) -> bool:
        """Set cached JSON value"""
        import json
        return await self.set(key, json.dumps(value), ttl)


# Global cache instance
cache = RedisCache()
