"""
SQLAlchemy initialization module.

Handles database creation and initial connection setup.
Does NOT define ORM models - that's PyDAL's responsibility.

This module is responsible for:
1. Creating database if it doesn't exist
2. Setting up connection pooling
3. Handling MariaDB Galera cluster settings
4. Verifying connectivity
5. Returning connection info for PyDAL
"""

import logging
from typing import Optional
from sqlalchemy import create_engine, text, inspect, NullPool, QueuePool
from sqlalchemy.exc import OperationalError, ProgrammingError
from shared.database.config import DatabaseConfig

logger = logging.getLogger(__name__)


def create_database_if_not_exists(config: DatabaseConfig) -> None:
    """
    Create database if it doesn't exist.

    For PostgreSQL and MySQL, connects to default database and creates
    target database if needed. SQLite databases are created automatically.
    """
    if config.db_type == 'sqlite':
        # SQLite creates database automatically
        logger.info(f"SQLite database will be created at: {config.name}")
        return

    # Connect to default database to create target database
    if config.db_type == 'postgres':
        default_db = 'postgres'
        driver = 'postgresql'
    elif config.db_type == 'mysql':
        default_db = 'mysql'
        driver = 'mysql+pymysql'
    else:
        raise ValueError(f"Unsupported db_type: {config.db_type}")

    # Build connection URL for default database
    default_url = (
        f"{driver}://{config.user}:{config.password}@"
        f"{config.host}:{config.port}/{default_db}"
    )

    # Create engine with NullPool to avoid connection pool issues
    engine = create_engine(default_url, poolclass=NullPool)

    try:
        with engine.connect() as conn:
            # Check if database exists
            if config.db_type == 'postgres':
                result = conn.execute(
                    text(
                        "SELECT 1 FROM pg_database "
                        "WHERE datname = :dbname"
                    ),
                    {'dbname': config.name}
                )
            else:  # MySQL
                result = conn.execute(
                    text(
                        "SELECT SCHEMA_NAME FROM "
                        "INFORMATION_SCHEMA.SCHEMATA "
                        "WHERE SCHEMA_NAME = :dbname"
                    ),
                    {'dbname': config.name}
                )

            if result.fetchone() is None:
                # Database doesn't exist, create it
                conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.execute(
                    text(f"CREATE DATABASE {config.name}")
                )
                logger.info(f"Created database: {config.name}")
            else:
                logger.info(f"Database already exists: {config.name}")

    except (OperationalError, ProgrammingError) as e:
        logger.error(f"Failed to create database: {e}")
        raise
    finally:
        engine.dispose()


def init_database() -> None:
    """
    Initialize database connection and create database if needed.

    This function should be called once at application startup.
    It creates the database if it doesn't exist and verifies connectivity.
    """
    config = DatabaseConfig.from_env()

    logger.info(f"Initializing database: {config.db_type}://{config.host or 'local'}:{config.port or 'N/A'}/{config.name}")

    # Create database if it doesn't exist
    create_database_if_not_exists(config)

    # Verify connection to target database
    verify_connection(config)

    logger.info("Database initialization complete")


def verify_connection(config: Optional[DatabaseConfig] = None) -> bool:
    """
    Verify database connection with test query.

    Args:
        config: Database configuration (loads from env if None)

    Returns:
        True if connection successful, raises exception otherwise

    Raises:
        OperationalError: If connection fails
    """
    if config is None:
        config = DatabaseConfig.from_env()

    url = config.to_sqlalchemy_url()
    kwargs = config.get_sqlalchemy_kwargs()

    engine = create_engine(url, **kwargs)

    try:
        with engine.connect() as conn:
            # Execute test query appropriate for database type
            if config.db_type == 'sqlite':
                result = conn.execute(text("SELECT 1"))
            elif config.db_type == 'postgres':
                result = conn.execute(text("SELECT 1 AS test"))
            else:  # MySQL
                result = conn.execute(text("SELECT 1 AS test"))

            test_value = result.scalar()
            if test_value == 1:
                logger.info("Database connection verified successfully")
                return True
            else:
                raise RuntimeError(
                    f"Unexpected test query result: {test_value}"
                )

    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        raise
    finally:
        engine.dispose()


def get_engine():
    """
    Create and return SQLAlchemy engine.

    This is primarily for advanced use cases. Most operations should use
    PyDAL via pydal_operations.py instead.

    Returns:
        SQLAlchemy Engine instance
    """
    config = DatabaseConfig.from_env()
    url = config.to_sqlalchemy_url()
    kwargs = config.get_sqlalchemy_kwargs()

    engine = create_engine(url, **kwargs)
    return engine
