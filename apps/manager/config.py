"""
Manager Service Configuration
"""
import os
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Config:
    """Manager service configuration with slots for memory efficiency"""

    # Database
    DATABASE_URL: str = os.environ.get(
        'DATABASE_URL',
        'postgresql://killkrill:killkrill123@postgres:5432/killkrill'
    )

    # Redis
    REDIS_URL: str = os.environ.get('REDIS_URL', 'redis://redis:6379')

    # Server
    HOST: str = os.environ.get('MANAGER_HOST', '0.0.0.0')
    PORT: int = int(os.environ.get('MANAGER_PORT', '8080'))

    # License
    LICENSE_KEY: str = os.environ.get('LICENSE_KEY', 'PENG-DEMO-DEMO-DEMO-DEMO-DEMO')

    # Logging
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')

    @property
    def pydal_database_url(self) -> str:
        """Convert PostgreSQL URL to PyDAL-compatible format"""
        return self.DATABASE_URL.replace('postgresql://', 'postgres://')


config = Config()
