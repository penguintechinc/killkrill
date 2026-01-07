"""
KillKrill API - Services
Business logic and external service integrations
"""

from .license_service import check_feature, get_license_info, init_license
from .redis_service import close_redis, get_redis, init_redis

__all__ = [
    "init_redis",
    "close_redis",
    "get_redis",
    "init_license",
    "check_feature",
    "get_license_info",
]
