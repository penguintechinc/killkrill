"""
KillKrill Flask Backend - SQLAlchemy Database Initialization Module

Handles database initialization with support for multiple database backends:
- PostgreSQL (default) with connection pooling
- MySQL/MariaDB with pymysql driver and Galera cluster support
- SQLite for development and testing

Note: This module handles ONLY initialization. PyDAL handles day-to-day operations.
"""

import os
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs
import logging

from sqlalchemy import (
    create_engine,
    Engine,
    event,
    text,
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.exc import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)


class DatabaseInitializationError(Exception):
    """Raised when database initialization fails"""

    pass


class DatabaseConfig:
    """
    Database configuration parser and validator
    """

    def __init__(self) -> None:
        """Initialize database configuration from environment"""
        self.db_type: str = os.getenv("DB_TYPE", "postgres").lower()
        self.database_url: str = os.getenv("DATABASE_URL", "")
        self.galera_mode: bool = os.getenv("GALERA_MODE", "false").lower() == "true"
        self.pool_size: int = int(os.getenv("DB_POOL_SIZE", "20"))
        self.max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.pool_pre_ping: bool = (
            os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
        )
        self.pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self.connect_timeout: int = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

        # Validate configuration
        self._validate()

    def _validate(self) -> None:
        """Validate database configuration"""
        if self.db_type not in ("postgres", "postgresql", "mysql", "mariadb", "sqlite"):
            raise DatabaseInitializationError(
                f"Unsupported DB_TYPE: {self.db_type}. "
                "Must be one of: postgres, mysql, mariadb, sqlite"
            )

        # SQLite doesn't need connection string
        if self.db_type == "sqlite":
            if not self.database_url:
                self.database_url = "sqlite:///killkrill.db"
        else:
            if not self.database_url:
                raise DatabaseInitializationError(
                    f"DATABASE_URL is required for {self.db_type}"
                )

        # Validate Galera mode is only for MySQL/MariaDB
        if self.galera_mode and self.db_type not in ("mysql", "mariadb"):
            logger.warning(
                "GALERA_MODE=true is only applicable for MySQL/MariaDB, ignoring"
            )
            self.galera_mode = False

    def __repr__(self) -> str:
        return (
            f"DatabaseConfig(db_type={self.db_type}, "
            f"galera_mode={self.galera_mode}, "
            f"pool_size={self.pool_size}, "
            f"max_overflow={self.max_overflow})"
        )


def _normalize_db_type(db_type: str) -> str:
    """Normalize database type string"""
    db_type = db_type.lower()
    if db_type == "postgresql":
        return "postgres"
    return db_type


def _apply_mysql_galera_settings(url: str) -> str:
    """
    Apply MariaDB Galera cluster settings to connection string.

    Adds wsrep_sync_wait parameter to ensure strong consistency in Galera clusters.
    This forces the database to wait for all nodes to apply transactions before
    returning to the client.
    """
    parsed = urlparse(url)

    # Parse existing query parameters
    query_params = parse_qs(parsed.query)

    # Add Galera-specific parameters
    # wsrep_sync_wait=15 enables full synchronous replication
    if "init_command" not in query_params:
        query_params["init_command"] = ["SET SESSION wsrep_sync_wait=15"]
    else:
        # Append if init_command already exists
        existing = query_params["init_command"][0]
        query_params["init_command"] = [f"{existing}; SET SESSION wsrep_sync_wait=15"]

    # Rebuild query string
    query_parts = []
    for key, values in query_params.items():
        for value in values:
            query_parts.append(f"{key}={value}")
    new_query = "&".join(query_parts)

    # Rebuild URL
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def _build_connection_string(config: DatabaseConfig) -> str:
    """
    Build normalized SQLAlchemy connection string.

    Handles dialect-specific adjustments and Galera cluster configuration.
    """
    db_url = config.database_url

    if config.db_type in ("postgres", "postgresql"):
        # Normalize postgresql:// to postgres://
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgres://", 1)
        logger.info("Using PostgreSQL database", url=_mask_url(db_url))

    elif config.db_type in ("mysql", "mariadb"):
        # Ensure proper MySQL dialect
        if db_url.startswith("mysql://"):
            db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
        elif db_url.startswith("mariadb://"):
            db_url = db_url.replace("mariadb://", "mysql+pymysql://", 1)
        elif not db_url.startswith("mysql+pymysql://"):
            # Try to detect and add pymysql
            if db_url.startswith("mysql"):
                db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)

        # Apply Galera settings if enabled
        if config.galera_mode:
            db_url = _apply_mysql_galera_settings(db_url)
            logger.info("MariaDB Galera cluster mode enabled")

        logger.info("Using MySQL/MariaDB database", url=_mask_url(db_url))

    elif config.db_type == "sqlite":
        logger.info("Using SQLite database", path=config.database_url)

    return db_url


def _mask_url(url: str, hide_password: bool = True) -> str:
    """
    Mask sensitive information in database URL for logging.

    Replaces password with asterisks for safe logging.
    """
    if not hide_password:
        return url

    parsed = urlparse(url)
    if parsed.password:
        # Replace password with masked version
        masked = parsed._replace(password="*" * 8 if parsed.password else None)
        return urlunparse(masked)
    return url


def _configure_pool(engine: Engine, config: DatabaseConfig) -> None:
    """
    Configure connection pool with appropriate settings for database backend.

    Applies pool settings, pre-ping for stale connections, and backend-specific
    configurations.
    """
    if isinstance(engine.pool, NullPool):
        logger.info("Using NullPool (no connection pooling)")
        return

    # Pool pre-ping for PostgreSQL and MySQL/MariaDB
    if config.pool_pre_ping and config.db_type != "sqlite":

        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Listener to test connection on checkout"""
            connection_record.info["fresh"] = True

        @event.listens_for(engine, "pre_execute")
        def receive_pre_execute(
            conn, clauseelement, multiparams, params, execution_options
        ):
            """Verify connection is alive before executing"""
            if not hasattr(conn, "info") or not conn.info.get("fresh"):
                try:
                    conn.connection.ping(False)
                except Exception:
                    conn.connection.ping(True)
                if hasattr(conn.info, "fresh"):
                    conn.info["fresh"] = True

        logger.info("Connection pool pre-ping enabled")

    # Pool recycle for long-lived connections
    if config.pool_recycle > 0:
        logger.info(
            "Connection pool recycle enabled", recycle_seconds=config.pool_recycle
        )


def _verify_database_connection(engine: Engine, config: DatabaseConfig) -> bool:
    """
    Verify database connection is working.

    Attempts to execute a simple query to validate the connection.
    """
    try:
        with engine.connect() as conn:
            if config.db_type in ("postgres", "postgresql"):
                result = conn.execute(text("SELECT 1 as connection_test"))
            elif config.db_type in ("mysql", "mariadb"):
                result = conn.execute(text("SELECT 1 as connection_test"))
            elif config.db_type == "sqlite":
                result = conn.execute(text("SELECT 1 as connection_test"))

            conn.commit()
            logger.info("Database connection verified successfully")
            return True

    except OperationalError as e:
        logger.error(
            "Failed to connect to database", error=str(e), db_type=config.db_type
        )
        return False
    except Exception as e:
        logger.error(
            "Unexpected error during database verification",
            error=str(e),
            db_type=config.db_type,
        )
        return False


def _create_database_if_needed(engine: Engine, config: DatabaseConfig) -> bool:
    """
    Create database if it doesn't exist.

    Only applicable for PostgreSQL and MySQL/MariaDB.
    SQLite creates the database file automatically.
    """
    if config.db_type == "sqlite":
        logger.info("SQLite database will be created automatically on first use")
        return True

    try:
        # Parse connection string to get database name
        parsed = urlparse(config.database_url)
        db_name = parsed.path.lstrip("/")

        if not db_name:
            logger.warning("Could not determine database name from connection string")
            return True

        if config.db_type in ("postgres", "postgresql"):
            # PostgreSQL: connect to default 'postgres' database to create target database
            default_url = config.database_url.rsplit("/", 1)[0] + "/postgres"
            admin_engine = create_engine(
                default_url.replace("postgresql://", "postgres://"),
                isolation_level="AUTOCOMMIT",
            )

            try:
                with admin_engine.connect() as conn:
                    # Check if database exists
                    result = conn.execute(
                        text(
                            f"SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = '{db_name}')"
                        )
                    )
                    db_exists = result.scalar()

                    if not db_exists:
                        conn.execute(text(f"CREATE DATABASE {db_name}"))
                        logger.info(f"Created PostgreSQL database: {db_name}")
                    else:
                        logger.info(f"PostgreSQL database already exists: {db_name}")
                    return True
            finally:
                admin_engine.dispose()

        elif config.db_type in ("mysql", "mariadb"):
            # MySQL/MariaDB: connect without database to create it
            base_url = config.database_url.rsplit("/", 1)[0]
            admin_engine = create_engine(
                base_url.replace("mysql://", "mysql+pymysql://")
            )

            try:
                with admin_engine.connect() as conn:
                    # Check if database exists
                    result = conn.execute(text(f"SHOW DATABASES LIKE '{db_name}'"))
                    db_exists = result.fetchone() is not None

                    if not db_exists:
                        conn.execute(text(f"CREATE DATABASE {db_name}"))
                        conn.commit()
                        logger.info(f"Created MySQL/MariaDB database: {db_name}")
                    else:
                        logger.info(f"MySQL/MariaDB database already exists: {db_name}")
                    return True
            finally:
                admin_engine.dispose()

    except ProgrammingError as e:
        logger.warning(
            "Could not create database (may not have permissions)",
            error=str(e),
            db_type=config.db_type,
        )
        return True  # Don't fail if we can't create, might have existing database
    except Exception as e:
        logger.error(
            "Unexpected error during database creation",
            error=str(e),
            db_type=config.db_type,
        )
        return False

    return True


def init_database() -> Tuple[Engine, DatabaseConfig]:
    """
    Initialize SQLAlchemy database engine with appropriate configuration.

    Reads configuration from environment variables:
    - DB_TYPE: postgres (default), mysql, mariadb, sqlite
    - DATABASE_URL: Connection string (required for non-SQLite)
    - GALERA_MODE: true/false for MariaDB Galera cluster mode
    - DB_POOL_SIZE: Connection pool size (default: 20)
    - DB_MAX_OVERFLOW: Additional connections beyond pool_size (default: 10)
    - DB_POOL_PRE_PING: Enable connection pre-ping (default: true)
    - DB_POOL_RECYCLE: Connection recycle time in seconds (default: 3600)
    - DB_CONNECT_TIMEOUT: Connection timeout in seconds (default: 10)

    Returns:
        Tuple[Engine, DatabaseConfig]: SQLAlchemy Engine and configuration object

    Raises:
        DatabaseInitializationError: If database initialization fails
    """
    logger.info("Initializing SQLAlchemy database connection")

    # Load and validate configuration
    config = DatabaseConfig()
    logger.info(f"Database configuration: {config}")

    try:
        # Build normalized connection string
        connection_string = _build_connection_string(config)

        # Determine pool configuration
        if config.db_type == "sqlite":
            # SQLite uses NullPool (no connection pooling)
            poolclass = NullPool
            pool_size = 0
            max_overflow = 0
            echo_pool = False
        else:
            # PostgreSQL and MySQL use QueuePool with connection pooling
            poolclass = QueuePool
            pool_size = config.pool_size
            max_overflow = config.max_overflow
            echo_pool = os.getenv("SQLALCHEMY_ECHO_POOL", "false").lower() == "true"

        logger.info(
            "Creating SQLAlchemy engine",
            db_type=config.db_type,
            pool_size=pool_size,
            max_overflow=max_overflow,
            poolclass=poolclass.__name__,
        )

        # Create engine
        engine = create_engine(
            connection_string,
            poolclass=poolclass,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=config.pool_pre_ping,
            pool_recycle=config.pool_recycle,
            echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
            echo_pool=echo_pool,
            connect_args=(
                {
                    "connect_timeout": config.connect_timeout,
                    "check_same_thread": False,  # Required for SQLite in some contexts
                }
                if config.db_type == "sqlite"
                else {
                    "connect_timeout": config.connect_timeout,
                }
            ),
        )

        logger.info("SQLAlchemy engine created successfully")

        # Configure pool behavior
        _configure_pool(engine, config)

        # Create database if it doesn't exist
        if not _create_database_if_needed(engine, config):
            raise DatabaseInitializationError(
                f"Failed to create {config.db_type} database"
            )

        # Verify database connection
        if not _verify_database_connection(engine, config):
            raise DatabaseInitializationError(
                f"Failed to verify connection to {config.db_type} database"
            )

        logger.info(
            "Database initialization completed successfully",
            db_type=config.db_type,
            connection=_mask_url(config.database_url),
        )

        return engine, config

    except DatabaseInitializationError:
        raise
    except Exception as e:
        logger.error(
            "Database initialization failed with unexpected error",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise DatabaseInitializationError(
            f"Failed to initialize database: {str(e)}"
        ) from e


def get_engine():
    """
    Get the database connection for operations.

    Returns the PyDAL connection for day-to-day database operations.
    This function is used by API blueprints to perform CRUD operations.

    Returns:
        DAL: PyDAL database abstraction layer instance with tables defined
    """
    # Return PyDAL connection for operations
    return get_pydal_connection()


# =============================================================================
# PyDAL Integration
# =============================================================================

_pydal_connection = None


def get_pydal_connection():
    """
    Get PyDAL connection for database operations.

    Creates a new PyDAL DAL instance with all table definitions.
    This function returns a PyDAL DAL object for day-to-day operations
    while SQLAlchemy handles initialization.

    Returns:
        DAL: PyDAL database abstraction layer instance with tables defined
    """
    global _pydal_connection

    if _pydal_connection is not None:
        return _pydal_connection

    try:
        from pydal import DAL, Field
        from pydal.validators import IS_NOT_EMPTY, IS_EMAIL, IS_IN_SET, IS_DATETIME
    except ImportError:
        logger.error("PyDAL not installed. Install with: pip install pydal")
        raise

    db_type = os.getenv("DB_TYPE", "postgres").lower()

    # Build PyDAL connection URI
    if db_type in ("postgres", "postgresql"):
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "killkrill")
        db_pass = os.getenv("DB_PASS", "killkrill123")
        db_name = os.getenv("DB_NAME", "killkrill")
        uri = f"postgres://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        folder = "/tmp/pydal_migrations"
    elif db_type in ("mysql", "mariadb"):
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "3306")
        db_user = os.getenv("DB_USER", "killkrill")
        db_pass = os.getenv("DB_PASS", "killkrill123")
        db_name = os.getenv("DB_NAME", "killkrill")
        uri = f"mysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        folder = "/tmp/pydal_migrations"
    elif db_type == "sqlite":
        db_path = os.getenv("DB_PATH", "/tmp/killkrill.db")
        uri = f"sqlite://{db_path}"
        folder = "/tmp/pydal_migrations"
    else:
        # Default to SQLite for safety
        uri = "sqlite:///tmp/killkrill.db"
        folder = "/tmp/pydal_migrations"

    # Ensure migrations folder exists
    os.makedirs(folder, exist_ok=True)

    logger.info(f"Connecting to PyDAL database: {db_type}")

    # Create PyDAL DAL instance
    # Note: check_reserved disabled as we control table/column naming internally
    db = DAL(
        uri,
        folder=folder,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        migrate=True,
        fake_migrate=False,
        check_reserved=[],  # Disable reserved keyword checks for internal tables
    )

    # Define all tables needed by API blueprints

    # Users table
    db.define_table(
        "users",
        Field("id", "string", length=64),
        Field("email", "string", length=255, unique=True),
        Field("password_hash", "string", length=255),
        Field("name", "string", length=255),
        Field("role", "string", length=32, default="viewer"),
        Field("is_active", "boolean", default=True),
        Field("fs_uniquifier", "string", length=64, unique=True),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # API Keys table
    db.define_table(
        "api_keys",
        Field("id", "string", length=64),
        Field("user_id", "string", length=64),
        Field("name", "string", length=128),
        Field("key_hash", "string", length=64),
        Field("permissions", "json"),
        Field("expires_at", "datetime"),
        Field("last_used_at", "datetime"),
        Field("is_active", "boolean", default=True),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # Audit Log table (note: 'action' renamed to 'audit_action' to avoid reserved keyword)
    db.define_table(
        "audit_log",
        Field("id", "string", length=64),
        Field("user_id", "string", length=64),
        Field("audit_action", "string", length=128),
        Field("resource_type", "string", length=64),
        Field("resource_id", "string", length=64),
        Field("details", "json"),
        Field("ip_address", "string", length=45),
        Field("user_agent", "string", length=512),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # Sensor Agents table (note: 'version' renamed to 'agent_version' to avoid reserved keyword)
    db.define_table(
        "sensor_agents",
        Field("id", "string", length=64),
        Field("agent_id", "string", length=64, unique=True),
        Field("name", "string", length=128),
        Field("hostname", "string", length=255),
        Field("ip_address", "string", length=45),
        Field("api_key_hash", "string", length=64),
        Field("agent_version", "string", length=32),
        Field("is_active", "boolean", default=True),
        Field("last_heartbeat", "datetime"),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # Sensor Checks table
    db.define_table(
        "sensor_checks",
        Field("id", "string", length=64),
        Field("name", "string", length=128),
        Field("check_type", "string", length=16),
        Field("target", "string", length=255),
        Field("port", "integer"),
        Field("interval_seconds", "integer", default=60),
        Field("timeout_seconds", "integer", default=30),
        Field("is_active", "boolean", default=True),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # Sensor Results table
    db.define_table(
        "sensor_results",
        Field("id", "string", length=64),
        Field("check_id", "string", length=64),
        Field("agent_id", "string", length=64),
        Field("status", "string", length=16),
        Field("response_time_ms", "integer"),
        Field("status_code", "integer"),
        Field("error_message", "string", length=1000),
        Field("ssl_valid", "boolean"),
        Field("ssl_expiry", "datetime"),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # Fleet Hosts table
    db.define_table(
        "fleet_hosts",
        Field("id", "string", length=64),
        Field("hostname", "string", length=255),
        Field("platform", "string", length=64),
        Field("os_version", "string", length=64),
        Field("agent_version", "string", length=32),
        Field("enrolled_at", "datetime"),
        Field("last_seen", "datetime"),
        Field("status", "string", length=16, default="online"),
        Field("labels", "json"),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # Fleet Queries table
    db.define_table(
        "fleet_queries",
        Field("id", "string", length=64),
        Field("name", "string", length=128),
        Field("query", "text"),
        Field("description", "text"),
        Field("schedule", "string", length=64),
        Field("is_active", "boolean", default=True),
        Field("created_by", "string", length=64),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # Fleet Policies table
    db.define_table(
        "fleet_policies",
        Field("id", "string", length=64),
        Field("name", "string", length=128),
        Field("description", "text"),
        Field("queries", "json"),
        Field("target_labels", "json"),
        Field("is_active", "boolean", default=True),
        Field("created_by", "string", length=64),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    # AI Analyses table
    db.define_table(
        "ai_analyses",
        Field("id", "string", length=64),
        Field("analysis_type", "string", length=32),
        Field("input_data", "json"),
        Field("result", "json"),
        Field("status", "string", length=16, default="pending"),
        Field("error_message", "text"),
        Field("created_by", "string", length=64),
        Field("created_at", "datetime"),
        Field("completed_at", "datetime"),
        migrate=True,
    )

    # AI Insights table
    db.define_table(
        "ai_insights",
        Field("id", "string", length=64),
        Field("analysis_id", "string", length=64),
        Field("insight_type", "string", length=32),
        Field("title", "string", length=255),
        Field("description", "text"),
        Field("priority", "string", length=16, default="medium"),
        Field("confidence", "double"),
        Field("metadata", "json"),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # AI Anomalies table
    db.define_table(
        "ai_anomalies",
        Field("id", "string", length=64),
        Field("analysis_id", "string", length=64),
        Field("anomaly_type", "string", length=32),
        Field("description", "text"),
        Field("severity", "string", length=16, default="medium"),
        Field("score", "double"),
        Field("source", "string", length=128),
        Field("metadata", "json"),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # AI Recommendations table
    db.define_table(
        "ai_recommendations",
        Field("id", "string", length=64),
        Field("analysis_id", "string", length=64),
        Field("title", "string", length=255),
        Field("description", "text"),
        Field("impact", "string", length=16, default="medium"),
        Field("actions", "json"),
        Field("metadata", "json"),
        Field("created_at", "datetime"),
        migrate=True,
    )

    # AI Providers table (configured AI endpoints for chat/analysis)
    # Free tier: 1 Ollama endpoint with tinyllama model only
    # Licensed tier: Multiple endpoints, OpenAI, Claude, custom models
    db.define_table(
        "ai_providers",
        Field("id", "string", length=64),
        Field("name", "string", length=128),
        Field("provider_type", "string", length=32),  # ollama, openai, claude
        Field("endpoint_url", "string", length=512),
        Field("api_key", "string", length=256),  # Encrypted/hashed in production
        Field("model", "string", length=128, default="tinyllama"),
        Field("is_default", "boolean", default=False),
        Field("is_active", "boolean", default=True),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=True,
    )

    logger.info("PyDAL tables defined successfully")

    _pydal_connection = db
    return db


# Alias for compatibility with blueprint imports
get_pydal_db = get_pydal_connection
