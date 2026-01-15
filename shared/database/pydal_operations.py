"""
PyDAL operations module.

Provides PyDAL database abstraction layer for day-to-day operations.
Handles thread-safe connections, context managers, and CRUD operations.
"""

import logging
import threading
from contextlib import contextmanager
from typing import Generator, Optional

from pydal import DAL, Field

from shared.database.config import DatabaseConfig

logger = logging.getLogger(__name__)

# Thread-local storage for database connections
_thread_local = threading.local()


def get_dal() -> DAL:
    """
    Get thread-local PyDAL instance.

    Returns:
        DAL instance for current thread

    Example:
        db = get_dal()
        users = db(db.users.email == 'test@example.com').select()
    """
    if not hasattr(_thread_local, "db"):
        config = DatabaseConfig.from_env()
        uri = config.to_pydal_uri()
        kwargs = config.get_pydal_kwargs()

        logger.debug(
            f"Creating new PyDAL connection for thread {threading.get_ident()}"
        )
        _thread_local.db = DAL(uri, **kwargs)

        # Define tables
        _define_tables(_thread_local.db)

    return _thread_local.db


def close_dal() -> None:
    """
    Close thread-local PyDAL connection.

    Should be called when thread is done with database operations.
    """
    if hasattr(_thread_local, "db"):
        logger.debug(f"Closing PyDAL connection for thread {threading.get_ident()}")
        _thread_local.db.close()
        delattr(_thread_local, "db")


@contextmanager
def dal_context() -> Generator[DAL, None, None]:
    """
    Context manager for PyDAL operations.

    Ensures connection is properly closed after use.

    Example:
        with dal_context() as db:
            users = db(db.users.email == 'test@example.com').select()
    """
    db = get_dal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        # Don't close here - let thread handle lifecycle
        pass


def _define_tables(db: DAL) -> None:
    """
    Define PyDAL tables with automatic migrations.

    This function defines all database tables used by Killkrill.
    PyDAL handles schema migrations automatically via migrate=True.

    Args:
        db: PyDAL instance
    """
    from shared.database.models import define_all_tables

    define_all_tables(db)


def execute_raw_sql(sql: str, params: Optional[dict] = None) -> list:
    """
    Execute raw SQL query with PyDAL.

    Args:
        sql: SQL query string
        params: Query parameters (optional)

    Returns:
        List of result rows

    Example:
        results = execute_raw_sql(
            "SELECT * FROM users WHERE email = :email",
            {"email": "test@example.com"}
        )
    """
    db = get_dal()
    return db.executesql(sql, placeholders=params or {})


def get_table_names() -> list[str]:
    """
    Get list of all table names in database.

    Returns:
        List of table names
    """
    db = get_dal()
    return db.tables


def drop_all_tables() -> None:
    """
    Drop all tables from database.

    WARNING: This is destructive and should only be used in tests.
    """
    db = get_dal()
    for table in reversed(db.tables):
        db[table].drop()
    db.commit()
    logger.warning("All tables dropped from database")


def reset_migrations() -> None:
    """
    Reset migration tracking.

    Useful for development when schema changes require fresh migrations.
    """
    import os

    config = DatabaseConfig.from_env()
    migration_folder = config.get_pydal_kwargs().get(
        "folder", "/tmp/killkrill-migrations/"
    )

    if os.path.exists(migration_folder):
        import shutil

        shutil.rmtree(migration_folder)
        logger.info(f"Migration folder reset: {migration_folder}")
