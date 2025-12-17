"""Flask configuration module with environment-based settings.

Provides base, development, production, and testing configurations with support for:
- Multi-database backends (PostgreSQL, MySQL, SQLite, etc.)
- Redis caching with optional TLS
- JWT and Flask-Security-Too authentication
- License server integration
- Monitoring and observability settings
- gRPC server configuration
- CORS policies

All settings are loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import os
from urllib.parse import quote


# Valid PyDAL database types for input validation
VALID_DB_TYPES = {
    "postgres",
    "postgresql",
    "mysql",
    "sqlite",
    "mssql",
    "oracle",
    "db2",
    "firebird",
    "informix",
    "ingres",
    "cubrid",
    "sapdb",
}


@dataclass(slots=True, frozen=True)
class DatabaseConfig:
    """Database configuration with support for multiple backends and connection pooling."""

    db_type: str
    host: str
    port: int
    user: str
    password: str
    name: str
    pool_size: int
    pool_recycle: int
    pool_pre_ping: bool
    galera_mode: bool = False
    echo: bool = False

    def __post_init__(self) -> None:
        """Validate database type after initialization."""
        if self.db_type not in VALID_DB_TYPES:
            raise ValueError(
                f"Invalid DB_TYPE: {self.db_type}. "
                f"Must be one of: {sorted(VALID_DB_TYPES)}"
            )

    def get_uri(self) -> str:
        """Build database connection URI.

        Returns:
            Connection URI appropriate for PyDAL or SQLAlchemy.

        Raises:
            ValueError: If database type is invalid.
        """
        # Normalize database type for PyDAL
        db_type_normalized = (
            "postgresql" if self.db_type == "postgres" else self.db_type
        )

        # URL-encode password to handle special characters
        encoded_password = quote(self.password, safe="")

        # SQLite has special handling (local file path)
        if self.db_type == "sqlite":
            return f"sqlite:///{self.name}"

        # Standard URI format for network databases
        return (
            f"{db_type_normalized}://{self.user}:{encoded_password}@"
            f"{self.host}:{self.port}/{self.name}"
        )

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        """Load database configuration from environment variables.

        Returns:
            DatabaseConfig instance with values from environment or defaults.
        """
        db_type = os.getenv("DB_TYPE", "postgres").lower()
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "5432"))
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASS", "")
        name = os.getenv("DB_NAME", "killkrill")
        pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
        galera_mode = os.getenv("GALERA_MODE", "false").lower() == "true"
        echo = os.getenv("DB_ECHO", "false").lower() == "true"

        return cls(
            db_type=db_type,
            host=host,
            port=port,
            user=user,
            password=password,
            name=name,
            pool_size=pool_size,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            galera_mode=galera_mode,
            echo=echo,
        )


@dataclass(slots=True, frozen=True)
class RedisConfig:
    """Redis/Valkey cache configuration with TLS support."""

    url: str
    socket_connect_timeout: int = 5
    socket_keepalive: bool = True
    socket_keepalive_options: dict[str, Any] = field(
        default_factory=lambda: {
            "TCP_KEEPIDLE": 60,
            "TCP_KEEPINTVL": 10,
            "TCP_KEEPCNT": 3,
        }
    )
    connection_pool_kwargs: dict[str, Any] = field(default_factory=dict)
    decode_responses: bool = True

    @classmethod
    def from_env(cls) -> RedisConfig:
        """Load Redis configuration from environment variables.

        Returns:
            RedisConfig instance with values from environment or default.

        Environment Variables:
            REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
        """
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return cls(url=url)


@dataclass(slots=True, frozen=True)
class JWTConfig:
    """JWT authentication configuration."""

    secret_key: str
    algorithm: str = "HS256"
    access_token_expires_minutes: int = 30
    refresh_token_expires_days: int = 7
    verify_signature: bool = True
    verify_exp: bool = True
    verify_nbf: bool = False
    verify_iat: bool = True
    verify_aud: bool = False

    @classmethod
    def from_env(cls) -> JWTConfig:
        """Load JWT configuration from environment variables.

        Returns:
            JWTConfig instance with values from environment or defaults.

        Environment Variables:
            SECRET_KEY: Secret key for JWT signing (required)
            JWT_SECRET: Alias for SECRET_KEY
            JWT_ALGORITHM: Token algorithm (default: HS256)
            JWT_ACCESS_TOKEN_EXPIRES_MINUTES: Token expiration (default: 30)
            JWT_REFRESH_TOKEN_EXPIRES_DAYS: Refresh token expiration (default: 7)
        """
        secret_key = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET", "")
        if not secret_key:
            raise ValueError(
                "SECRET_KEY or JWT_SECRET environment variable must be set"
            )

        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        access_token_expires = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "30")
        )
        refresh_token_expires = int(
            os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "7")
        )

        return cls(
            secret_key=secret_key,
            algorithm=algorithm,
            access_token_expires_minutes=access_token_expires,
            refresh_token_expires_days=refresh_token_expires,
        )


@dataclass(slots=True, frozen=True)
class FlaskSecurityConfig:
    """Flask-Security-Too configuration for authentication and authorization."""

    password_salt: str
    bcrypt_log_rounds: int = 12
    password_schemes: tuple[str, ...] = ("bcrypt", "plaintext")
    deprecated_password_schemes: tuple[str, ...] = ("plaintext",)
    hashing_algorithms: dict[str, str] = field(
        default_factory=lambda: {
            "pbkdf2_sha512": "default",
            "argon2": "argon2",
        }
    )
    remember_cookie_secure: bool = True
    remember_cookie_httponly: bool = True
    remember_cookie_samesite: str = "Strict"
    remember_cookie_duration: int = 2592000  # 30 days
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "Strict"
    session_cookie_name: str = "session"
    user_identity_attributes: tuple[str, ...] = ("email", "username")

    @classmethod
    def from_env(cls) -> FlaskSecurityConfig:
        """Load Flask-Security-Too configuration from environment variables.

        Returns:
            FlaskSecurityConfig instance with values from environment or defaults.

        Environment Variables:
            SECURITY_PASSWORD_SALT: Salt for password hashing (required)
            SECURITY_BCRYPT_LOG_ROUNDS: Bcrypt rounds (default: 12)
        """
        password_salt = os.getenv("SECURITY_PASSWORD_SALT", "")
        if not password_salt:
            raise ValueError(
                "SECURITY_PASSWORD_SALT environment variable must be set"
            )

        bcrypt_rounds = int(os.getenv("SECURITY_BCRYPT_LOG_ROUNDS", "12"))

        return cls(
            password_salt=password_salt,
            bcrypt_log_rounds=bcrypt_rounds,
        )


@dataclass(slots=True, frozen=True)
class LicenseConfig:
    """PenguinTech License Server integration configuration."""

    license_key: str
    server_url: str
    product_name: str
    enabled: bool
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls) -> LicenseConfig:
        """Load license configuration from environment variables.

        Returns:
            LicenseConfig instance with values from environment or defaults.

        Environment Variables:
            LICENSE_KEY: License key (PENG-XXXX-XXXX-XXXX-XXXX-ABCD format)
            LICENSE_SERVER_URL: License server URL (default: https://license.penguintech.io)
            PRODUCT_NAME: Product identifier for license validation
            RELEASE_MODE: Enable license enforcement (default: false)
        """
        license_key = os.getenv("LICENSE_KEY", "")
        server_url = os.getenv(
            "LICENSE_SERVER_URL", "https://license.penguintech.io"
        )
        product_name = os.getenv("PRODUCT_NAME", "killkrill")
        release_mode = os.getenv("RELEASE_MODE", "false").lower() == "true"

        return cls(
            license_key=license_key,
            server_url=server_url,
            product_name=product_name,
            enabled=release_mode and bool(license_key),
        )


@dataclass(slots=True, frozen=True)
class MonitoringConfig:
    """Monitoring and observability configuration."""

    prometheus_url: str
    elasticsearch_url: str
    grafana_url: str
    enable_metrics: bool = True
    enable_tracing: bool = False
    metrics_port: int = 8001
    tracing_sample_rate: float = 0.1

    @classmethod
    def from_env(cls) -> MonitoringConfig:
        """Load monitoring configuration from environment variables.

        Returns:
            MonitoringConfig instance with values from environment or defaults.
        """
        prometheus_url = os.getenv(
            "PROMETHEUS_URL", "http://localhost:9090"
        )
        elasticsearch_url = os.getenv(
            "ELASTICSEARCH_URL", "http://localhost:9200"
        )
        grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
        enable_metrics = (
            os.getenv("ENABLE_METRICS", "true").lower() == "true"
        )
        enable_tracing = (
            os.getenv("ENABLE_TRACING", "false").lower() == "true"
        )
        metrics_port = int(os.getenv("METRICS_PORT", "8001"))
        tracing_sample_rate = float(
            os.getenv("TRACING_SAMPLE_RATE", "0.1")
        )

        return cls(
            prometheus_url=prometheus_url,
            elasticsearch_url=elasticsearch_url,
            grafana_url=grafana_url,
            enable_metrics=enable_metrics,
            enable_tracing=enable_tracing,
            metrics_port=metrics_port,
            tracing_sample_rate=tracing_sample_rate,
        )


@dataclass(slots=True, frozen=True)
class GRPCConfig:
    """gRPC server configuration."""

    port: int = 50051
    host: str = "0.0.0.0"
    max_workers: int = 10
    max_concurrent_rpcs: Optional[int] = None
    keepalive_time_ms: int = 30000
    keepalive_timeout_ms: int = 10000
    max_message_length: int = 4 * 1024 * 1024  # 4MB

    @classmethod
    def from_env(cls) -> GRPCConfig:
        """Load gRPC configuration from environment variables.

        Returns:
            GRPCConfig instance with values from environment or defaults.

        Environment Variables:
            GRPC_PORT: gRPC server port (default: 50051)
            GRPC_HOST: gRPC server bind address (default: 0.0.0.0)
            GRPC_MAX_WORKERS: Thread pool workers (default: 10)
        """
        port = int(os.getenv("GRPC_PORT", "50051"))
        host = os.getenv("GRPC_HOST", "0.0.0.0")
        max_workers = int(os.getenv("GRPC_MAX_WORKERS", "10"))

        return cls(port=port, host=host, max_workers=max_workers)


@dataclass(slots=True, frozen=True)
class CORSConfig:
    """Cross-Origin Resource Sharing (CORS) configuration."""

    allow_origins: list[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH"]
    )
    allow_headers: list[str] = field(
        default_factory=lambda: ["*"]
    )
    expose_headers: list[str] = field(
        default_factory=lambda: [
            "Content-Range",
            "X-Total-Count",
            "X-Page-Count",
        ]
    )
    max_age: int = 3600

    @classmethod
    def from_env(cls) -> CORSConfig:
        """Load CORS configuration from environment variables.

        Returns:
            CORSConfig instance with values from environment or defaults.

        Environment Variables:
            CORS_ALLOW_ORIGINS: Comma-separated list of allowed origins
            CORS_ALLOW_CREDENTIALS: Allow credentials in CORS requests
        """
        origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
        origins = [o.strip() for o in origins]
        allow_credentials = (
            os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
        )

        return cls(
            allow_origins=origins,
            allow_credentials=allow_credentials,
        )


@dataclass(slots=True, frozen=True)
class BaseConfig:
    """Base Flask configuration with common settings for all environments."""

    app_name: str = "killkrill"
    debug: bool = False
    testing: bool = False
    environment: str = "development"
    log_level: str = "INFO"

    # Flask core settings
    json_sort_keys: bool = False
    jsonify_prettyprint_regular: bool = True
    permanent_session_lifetime: int = 2592000  # 30 days
    send_file_max_age_default: int = 604800  # 7 days

    # Nested configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig.from_env)
    redis: RedisConfig = field(default_factory=RedisConfig.from_env)
    jwt: JWTConfig = field(default_factory=JWTConfig.from_env)
    security: FlaskSecurityConfig = field(
        default_factory=FlaskSecurityConfig.from_env
    )
    license: LicenseConfig = field(default_factory=LicenseConfig.from_env)
    monitoring: MonitoringConfig = field(
        default_factory=MonitoringConfig.from_env
    )
    grpc: GRPCConfig = field(default_factory=GRPCConfig.from_env)
    cors: CORSConfig = field(default_factory=CORSConfig.from_env)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for Flask.config.update().

        Returns:
            Dictionary of top-level configuration values suitable for Flask.
        """
        return {
            "APP_NAME": self.app_name,
            "DEBUG": self.debug,
            "TESTING": self.testing,
            "ENV": self.environment,
            "LOG_LEVEL": self.log_level,
            "JSON_SORT_KEYS": self.json_sort_keys,
            "JSONIFY_PRETTYPRINT_REGULAR": self.jsonify_prettyprint_regular,
            "PERMANENT_SESSION_LIFETIME": self.permanent_session_lifetime,
            "SEND_FILE_MAX_AGE_DEFAULT": self.send_file_max_age_default,
            # Nested configs
            "DATABASE": self.database,
            "REDIS": self.redis,
            "JWT": self.jwt,
            "SECURITY": self.security,
            "LICENSE": self.license,
            "MONITORING": self.monitoring,
            "GRPC": self.grpc,
            "CORS": self.cors,
        }


@dataclass(slots=True, frozen=True)
class DevelopmentConfig(BaseConfig):
    """Development environment configuration with verbose logging and debugging."""

    debug: bool = True
    testing: bool = False
    environment: str = "development"
    log_level: str = "DEBUG"
    jsonify_prettyprint_regular: bool = True


@dataclass(slots=True, frozen=True)
class ProductionConfig(BaseConfig):
    """Production environment configuration with strict security settings."""

    debug: bool = False
    testing: bool = False
    environment: str = "production"
    log_level: str = "WARNING"
    jsonify_prettyprint_regular: bool = False


def _get_test_database() -> DatabaseConfig:
    """Create test database configuration with in-memory SQLite."""
    return DatabaseConfig(
        db_type="sqlite",
        host="",
        port=0,
        user="",
        password="",
        name=":memory:",
        pool_size=1,
        pool_recycle=3600,
        pool_pre_ping=True,
        galera_mode=False,
        echo=False,
    )


@dataclass(slots=True, frozen=True)
class TestingConfig(BaseConfig):
    """Testing environment configuration with test database and disabled features."""

    debug: bool = True
    testing: bool = True
    environment: str = "testing"
    log_level: str = "DEBUG"
    permanent_session_lifetime: int = 300
    send_file_max_age_default: int = 0
    database: DatabaseConfig = field(default_factory=_get_test_database)


def get_config(environment: Optional[str] = None) -> BaseConfig:
    """Get configuration instance for the specified environment.

    Args:
        environment: Configuration environment name ('development', 'production',
                    'testing'). If None, reads from FLASK_ENV environment variable
                    with 'development' as default.

    Returns:
        Configuration object for the specified environment.

    Raises:
        ValueError: If environment is not recognized.
    """
    if environment is None:
        environment = os.getenv("FLASK_ENV", "development").lower()

    config_map: dict[str, type[BaseConfig]] = {
        "development": DevelopmentConfig,
        "dev": DevelopmentConfig,
        "production": ProductionConfig,
        "prod": ProductionConfig,
        "testing": TestingConfig,
        "test": TestingConfig,
    }

    if environment not in config_map:
        raise ValueError(
            f"Unknown environment: {environment}. "
            f"Must be one of: {', '.join(config_map.keys())}"
        )

    return config_map[environment]()
