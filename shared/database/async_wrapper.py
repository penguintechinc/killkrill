"""
Async wrapper for PyDAL operations.

Provides async/await interface for database operations using run_in_executor.
PyDAL is synchronous, so we wrap operations in thread pool execution.
"""

import asyncio
import logging
from typing import Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pydal import DAL
from shared.database.pydal_operations import get_dal, close_dal

logger = logging.getLogger(__name__)

# Global thread pool for database operations
_executor: Optional[ThreadPoolExecutor] = None
_executor_max_workers = 10


def get_executor() -> ThreadPoolExecutor:
    """
    Get or create thread pool executor for async database operations.

    Returns:
        ThreadPoolExecutor instance
    """
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=_executor_max_workers,
            thread_name_prefix='db_async_'
        )
    return _executor


def shutdown_executor() -> None:
    """Shutdown thread pool executor."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


class AsyncDatabase:
    """
    Async wrapper for PyDAL operations.

    Provides async/await interface by running PyDAL operations in
    ThreadPoolExecutor using run_in_executor.

    Example:
        async_db = AsyncDatabase()
        users = await async_db.async_select('auth_user', db.auth_user.email == 'test@example.com')
    """

    def __init__(self, executor: Optional[ThreadPoolExecutor] = None):
        """
        Initialize async database wrapper.

        Args:
            executor: Optional ThreadPoolExecutor (uses global if None)
        """
        self.executor = executor or get_executor()

    async def _run_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Run synchronous function in thread pool.

        Args:
            func: Synchronous function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: func(*args, **kwargs)
        )

    async def async_select(
        self,
        table_name: str,
        query: Optional[Any] = None,
        **select_kwargs
    ) -> list:
        """
        Async select operation.

        Args:
            table_name: Table name
            query: PyDAL query expression
            **select_kwargs: Additional arguments for .select()

        Returns:
            List of rows

        Example:
            users = await async_db.async_select(
                'auth_user',
                db.auth_user.active == True,
                orderby=~db.auth_user.created_at
            )
        """
        def _select():
            db = get_dal()
            table = db[table_name]
            if query is not None:
                return db(query).select(**select_kwargs).as_list()
            else:
                return db(table).select(**select_kwargs).as_list()

        return await self._run_sync(_select)

    async def async_insert(self, table_name: str, **fields) -> int:
        """
        Async insert operation.

        Args:
            table_name: Table name
            **fields: Field values

        Returns:
            ID of inserted record

        Example:
            user_id = await async_db.async_insert(
                'auth_user',
                email='test@example.com',
                password='hashed_password'
            )
        """
        def _insert():
            db = get_dal()
            table = db[table_name]
            record_id = table.insert(**fields)
            db.commit()
            return record_id

        return await self._run_sync(_insert)

    async def async_update(
        self,
        table_name: str,
        query: Any,
        **fields
    ) -> int:
        """
        Async update operation.

        Args:
            table_name: Table name
            query: PyDAL query expression
            **fields: Fields to update

        Returns:
            Number of updated rows

        Example:
            updated = await async_db.async_update(
                'auth_user',
                db.auth_user.email == 'test@example.com',
                active=False
            )
        """
        def _update():
            db = get_dal()
            updated = db(query).update(**fields)
            db.commit()
            return updated

        return await self._run_sync(_update)

    async def async_delete(self, table_name: str, query: Any) -> int:
        """
        Async delete operation.

        Args:
            table_name: Table name
            query: PyDAL query expression

        Returns:
            Number of deleted rows

        Example:
            deleted = await async_db.async_delete(
                'auth_user',
                db.auth_user.email == 'test@example.com'
            )
        """
        def _delete():
            db = get_dal()
            deleted = db(query).delete()
            db.commit()
            return deleted

        return await self._run_sync(_delete)

    async def async_count(self, table_name: str, query: Optional[Any] = None) -> int:
        """
        Async count operation.

        Args:
            table_name: Table name
            query: Optional PyDAL query expression

        Returns:
            Count of rows

        Example:
            count = await async_db.async_count('auth_user', db.auth_user.active == True)
        """
        def _count():
            db = get_dal()
            table = db[table_name]
            if query is not None:
                return db(query).count()
            else:
                return db(table).count()

        return await self._run_sync(_count)

    async def async_validate_and_insert(
        self,
        table_name: str,
        **fields
    ) -> dict:
        """
        Async validate and insert with error handling.

        Args:
            table_name: Table name
            **fields: Field values

        Returns:
            Dict with 'id' if successful, 'errors' if validation fails

        Example:
            result = await async_db.async_validate_and_insert(
                'auth_user',
                email='test@example.com',
                password='hashed_password'
            )
            if 'errors' in result:
                print(result['errors'])
        """
        def _validate_and_insert():
            db = get_dal()
            table = db[table_name]
            result = table.validate_and_insert(**fields)
            if result.errors:
                db.rollback()
                return {'errors': result.errors}
            else:
                db.commit()
                return {'id': result.id}

        return await self._run_sync(_validate_and_insert)

    async def async_validate_and_update(
        self,
        table_name: str,
        query: Any,
        **fields
    ) -> dict:
        """
        Async validate and update with error handling.

        Args:
            table_name: Table name
            query: PyDAL query expression
            **fields: Fields to update

        Returns:
            Dict with 'updated' count if successful, 'errors' if validation fails
        """
        def _validate_and_update():
            db = get_dal()
            table = db[table_name]

            # Get first matching record
            record = db(query).select().first()
            if not record:
                return {'errors': {'record': 'Not found'}}

            # Validate update
            result = table.validate_and_update(record.id, **fields)
            if result.errors:
                db.rollback()
                return {'errors': result.errors}
            else:
                db.commit()
                return {'updated': 1}

        return await self._run_sync(_validate_and_update)

    async def async_executesql(
        self,
        sql: str,
        params: Optional[dict] = None
    ) -> list:
        """
        Execute raw SQL asynchronously.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of result rows

        Example:
            results = await async_db.async_executesql(
                "SELECT * FROM auth_user WHERE email = :email",
                {"email": "test@example.com"}
            )
        """
        def _executesql():
            db = get_dal()
            return db.executesql(sql, placeholders=params or {})

        return await self._run_sync(_executesql)


@asynccontextmanager
async def async_dal_context():
    """
    Async context manager for database operations.

    Ensures proper cleanup after async operations.

    Example:
        async with async_dal_context() as async_db:
            users = await async_db.async_select('auth_user')
    """
    async_db = AsyncDatabase()
    try:
        yield async_db
    finally:
        # Cleanup handled by thread-local storage
        pass
