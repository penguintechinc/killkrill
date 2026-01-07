"""
Shared database module for Killkrill.

This module provides a hybrid database approach:
- SQLAlchemy: Database creation and initial connection setup
- PyDAL: Day-to-day CRUD operations and migrations

Architecture:
1. Use sqlalchemy_init.py to create database and verify connectivity
2. Use pydal_operations.py for all CRUD operations
3. Use async_wrapper.py for async database operations
4. Define all tables in models.py

Example Usage:
    from shared.database import init_database, get_dal, AsyncDatabase

    # Initialize database (run once at startup)
    init_database()

    # Get PyDAL instance for sync operations
    db = get_dal()

    # Async operations
    async_db = AsyncDatabase()
    users = await async_db.async_select('users', db.users.email == 'test@example.com')
"""

from shared.database.sqlalchemy_init import init_database, verify_connection
from shared.database.pydal_operations import get_dal, close_dal, dal_context
from shared.database.async_wrapper import AsyncDatabase
from shared.database.config import DatabaseConfig

__all__ = [
    'init_database',
    'verify_connection',
    'get_dal',
    'close_dal',
    'dal_context',
    'AsyncDatabase',
    'DatabaseConfig',
]
