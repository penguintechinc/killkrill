"""
KillKrill API Configuration Management
Environment-based configuration with sensible defaults
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List
from decouple import config


@dataclass
class QuartConfig:
    """Quart application configuration"""

    # Application
    SECRET_KEY: str = field(default_factory=lambda: config(
        'SECRET_KEY', default='killkrill-dev-secret-change-in-production'
    ))
    DEBUG: bool = field(default_factory=lambda: config('DEBUG', default=False, cast=bool))
    TESTING: bool = False

    # Database (PyDAL)
    DATABASE_URL: str = field(default_factory=lambda: config(
        'DATABASE_URL',
        default='postgresql://killkrill:killkrill123@localhost:5432/killkrill'
    ))
    DB_POOL_SIZE: int = field(default_factory=lambda: config('DB_POOL_SIZE', default=10, cast=int))
    DB_MIGRATE: bool = field(default_factory=lambda: config('DB_MIGRATE', default=True, cast=bool))

    # Redis
    REDIS_URL: str = field(default_factory=lambda: config(
        'REDIS_URL', default='redis://localhost:6379/0'
    ))
    REDIS_MAX_CONNECTIONS: int = field(default_factory=lambda: config(
        'REDIS_MAX_CONNECTIONS', default=20, cast=int
    ))

    # JWT Authentication
    JWT_SECRET: str = field(default_factory=lambda: config(
        'JWT_SECRET', default='killkrill-jwt-secret-change-in-production'
    ))
    JWT_ACCESS_TOKEN_EXPIRES: int = field(default_factory=lambda: config(
        'JWT_ACCESS_TOKEN_EXPIRES', default=3600, cast=int  # 1 hour
    ))
    JWT_REFRESH_TOKEN_EXPIRES: int = field(default_factory=lambda: config(
        'JWT_REFRESH_TOKEN_EXPIRES', default=604800, cast=int  # 7 days
    ))

    # License Server
    LICENSE_KEY: str = field(default_factory=lambda: config('LICENSE_KEY', default=''))
    PRODUCT_NAME: str = field(default_factory=lambda: config('PRODUCT_NAME', default='killkrill'))
    LICENSE_SERVER_URL: str = field(default_factory=lambda: config(
        'LICENSE_SERVER_URL', default='https://license.penguintech.io'
    ))

    # CORS
    CORS_ORIGINS: str = field(default_factory=lambda: config('CORS_ORIGINS', default='*'))

    # Rate Limiting
    RATE_LIMIT_DEFAULT: str = field(default_factory=lambda: config(
        'RATE_LIMIT_DEFAULT', default='100/minute'
    ))

    # External Services
    PROMETHEUS_URL: str = field(default_factory=lambda: config(
        'PROMETHEUS_URL', default='http://prometheus:9090'
    ))
    ELASTICSEARCH_URL: str = field(default_factory=lambda: config(
        'ELASTICSEARCH_URL', default='http://elasticsearch:9200'
    ))
    KIBANA_URL: str = field(default_factory=lambda: config(
        'KIBANA_URL', default='http://kibana:5601'
    ))
    GRAFANA_URL: str = field(default_factory=lambda: config(
        'GRAFANA_URL', default='http://grafana:3000'
    ))
    ALERTMANAGER_URL: str = field(default_factory=lambda: config(
        'ALERTMANAGER_URL', default='http://alertmanager:9093'
    ))
    FLEET_SERVER_URL: str = field(default_factory=lambda: config(
        'FLEET_SERVER_URL', default='http://fleet-server:8080'
    ))
    FLEET_API_TOKEN: str = field(default_factory=lambda: config('FLEET_API_TOKEN', default=''))

    # Internal Services
    LOG_RECEIVER_URL: str = field(default_factory=lambda: config(
        'LOG_RECEIVER_URL', default='http://log-receiver:8081'
    ))
    METRICS_RECEIVER_URL: str = field(default_factory=lambda: config(
        'METRICS_RECEIVER_URL', default='http://metrics-receiver:8082'
    ))

    # Logging
    LOG_LEVEL: str = field(default_factory=lambda: config('LOG_LEVEL', default='INFO'))

    # Server
    HOST: str = field(default_factory=lambda: config('HOST', default='0.0.0.0'))
    PORT: int = field(default_factory=lambda: config('PORT', default=8080, cast=int))
    WORKERS: int = field(default_factory=lambda: config('WORKERS', default=4, cast=int))

    @classmethod
    def get_config(cls, env: str = None) -> 'QuartConfig':
        """Get configuration based on environment"""
        env = env or os.getenv('FLASK_ENV', 'development')

        if env == 'production':
            return ProductionConfig()
        elif env == 'testing':
            return TestingConfig()
        else:
            return DevelopmentConfig()


@dataclass
class DevelopmentConfig(QuartConfig):
    """Development configuration"""
    DEBUG: bool = True
    LOG_LEVEL: str = 'DEBUG'


@dataclass
class ProductionConfig(QuartConfig):
    """Production configuration"""
    DEBUG: bool = False
    LOG_LEVEL: str = 'INFO'


@dataclass
class TestingConfig(QuartConfig):
    """Testing configuration"""
    TESTING: bool = True
    DEBUG: bool = True
    DATABASE_URL: str = 'sqlite:memory:'
    DB_MIGRATE: bool = True


# Global config instance
_config: Optional[QuartConfig] = None


def get_config() -> QuartConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = QuartConfig.get_config()
    return _config


def reload_config(env: str = None) -> QuartConfig:
    """Reload configuration"""
    global _config
    _config = QuartConfig.get_config(env)
    return _config
