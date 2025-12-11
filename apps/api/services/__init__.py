"""
KillKrill API - Services
Business logic and external service integrations
"""

from .redis_service import init_redis, close_redis, get_redis
from .license_service import init_license, check_feature, get_license_info

__all__ = [
    'init_redis',
    'close_redis',
    'get_redis',
    'init_license',
    'check_feature',
    'get_license_info',
]
