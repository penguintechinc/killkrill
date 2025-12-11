"""
KillKrill API - PyDAL Database Connection Manager
Async-compatible connection pooling for Quart
"""

import asyncio
from datetime import datetime
from typing import Optional, List
from contextvars import ContextVar

from pydal import DAL, Field
from quart import Quart
import structlog

from config import get_config

logger = structlog.get_logger(__name__)

# Context variable for async-safe database access
_db_context: ContextVar[Optional[DAL]] = ContextVar('db', default=None)

# Global database manager
_db_manager: Optional['DatabaseManager'] = None


class DatabaseManager:
    """
    Manages PyDAL connections in async context with connection pooling
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self._pool: List[DAL] = []
        self._pool_size = self.config.DB_POOL_SIZE
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize connection pool"""
        if self._initialized:
            return

        # Convert PostgreSQL URL for PyDAL compatibility
        db_url = self.config.DATABASE_URL
        if db_url.startswith('postgresql://'):
            db_url = db_url.replace('postgresql://', 'postgres://')

        logger.info("initializing_database", pool_size=self._pool_size)

        # Create initial connections
        for i in range(self._pool_size):
            try:
                db = DAL(
                    db_url,
                    pool_size=1,
                    migrate=self.config.DB_MIGRATE,
                    fake_migrate=False,
                    lazy_tables=True
                )
                self._define_tables(db)
                self._pool.append(db)
                logger.debug("database_connection_created", connection_id=i)
            except Exception as e:
                logger.error("database_connection_failed", error=str(e), connection_id=i)
                raise

        self._initialized = True
        logger.info("database_initialized", connections=len(self._pool))

    def _define_tables(self, db: DAL) -> None:
        """Define all database tables"""

        # Health checks table
        db.define_table('health_checks',
            Field('timestamp', 'datetime', default=datetime.utcnow),
            Field('status', 'string', length=50, default='ok'),
            Field('component', 'string', length=100),
            Field('details', 'text'),
            migrate=True
        )

        # Users table
        db.define_table('users',
            Field('username', 'string', length=100, unique=True, notnull=True),
            Field('email', 'string', length=255, unique=True, notnull=True),
            Field('password_hash', 'string', length=255, notnull=True),
            Field('first_name', 'string', length=100),
            Field('last_name', 'string', length=100),
            Field('role', 'string', length=50, default='user'),
            Field('is_active', 'boolean', default=True),
            Field('created_at', 'datetime', default=datetime.utcnow),
            Field('updated_at', 'datetime', default=datetime.utcnow, update=datetime.utcnow),
            Field('last_login', 'datetime'),
            migrate=True
        )

        # API Keys table
        db.define_table('api_keys',
            Field('user_id', 'reference users', notnull=True),
            Field('name', 'string', length=100, notnull=True),
            Field('key_hash', 'string', length=255, notnull=True),
            Field('permissions', 'text'),  # JSON array of permissions
            Field('is_active', 'boolean', default=True),
            Field('created_at', 'datetime', default=datetime.utcnow),
            Field('expires_at', 'datetime'),
            Field('last_used', 'datetime'),
            migrate=True
        )

        # Refresh tokens table
        db.define_table('refresh_tokens',
            Field('user_id', 'reference users', notnull=True),
            Field('token_hash', 'string', length=255, unique=True, notnull=True),
            Field('created_at', 'datetime', default=datetime.utcnow),
            Field('expires_at', 'datetime', notnull=True),
            Field('revoked', 'boolean', default=False),
            Field('revoked_at', 'datetime'),
            migrate=True
        )

        # License usage tracking
        db.define_table('license_usage',
            Field('feature_name', 'string', length=100, notnull=True),
            Field('user_id', 'reference users'),
            Field('usage_count', 'integer', default=1),
            Field('last_used', 'datetime', default=datetime.utcnow),
            migrate=True
        )

        # Sensor agents table
        db.define_table('sensor_agents',
            Field('agent_id', 'string', length=100, unique=True, notnull=True),
            Field('name', 'string', length=200, notnull=True),
            Field('location', 'string', length=200),
            Field('api_key_hash', 'string', length=255, notnull=True),
            Field('is_active', 'boolean', default=True),
            Field('last_heartbeat', 'datetime'),
            Field('created_at', 'datetime', default=datetime.utcnow),
            Field('metadata', 'text'),  # JSON additional metadata
            migrate=True
        )

        # Sensor checks configuration
        db.define_table('sensor_checks',
            Field('check_id', 'string', length=100, unique=True, notnull=True),
            Field('name', 'string', length=200, notnull=True),
            Field('check_type', 'string', length=50, notnull=True),  # tcp, http, https, dns
            Field('target', 'string', length=500, notnull=True),
            Field('port', 'integer'),
            Field('path', 'string', length=500),
            Field('expected_status', 'integer'),
            Field('timeout_ms', 'integer', default=5000),
            Field('interval_seconds', 'integer', default=60),
            Field('headers', 'text'),  # JSON headers
            Field('is_active', 'boolean', default=True),
            Field('created_at', 'datetime', default=datetime.utcnow),
            Field('updated_at', 'datetime', default=datetime.utcnow, update=datetime.utcnow),
            migrate=True
        )

        # Sensor results
        db.define_table('sensor_results',
            Field('agent_id', 'string', length=100, notnull=True),
            Field('check_id', 'string', length=100, notnull=True),
            Field('timestamp', 'datetime', default=datetime.utcnow),
            Field('status', 'string', length=50, notnull=True),  # up, down, timeout, error
            Field('response_time_ms', 'integer'),
            Field('status_code', 'integer'),
            Field('error_message', 'text'),
            Field('ssl_expiry', 'datetime'),
            Field('ssl_valid', 'boolean'),
            migrate=True
        )

        # AI analyses (enterprise feature)
        db.define_table('ai_analyses',
            Field('analysis_id', 'string', length=100, unique=True, notnull=True),
            Field('timestamp', 'datetime', default=datetime.utcnow),
            Field('analysis_type', 'string', length=100),
            Field('severity', 'string', length=50),
            Field('summary', 'text'),
            Field('recommendations', 'text'),
            Field('affected_components', 'text'),  # JSON array
            Field('metrics_analyzed', 'text'),  # JSON object
            Field('confidence_score', 'double'),
            Field('is_acknowledged', 'boolean', default=False),
            Field('acknowledged_by', 'string', length=100),
            Field('acknowledged_at', 'datetime'),
            migrate=True
        )

        # Audit log
        db.define_table('audit_log',
            Field('timestamp', 'datetime', default=datetime.utcnow),
            Field('user_id', 'reference users'),
            Field('action', 'string', length=100, notnull=True),
            Field('resource_type', 'string', length=100),
            Field('resource_id', 'string', length=100),
            Field('details', 'text'),  # JSON
            Field('ip_address', 'string', length=45),
            Field('user_agent', 'text'),
            migrate=True
        )

        db.commit()

    async def get_connection(self) -> DAL:
        """Get a database connection from pool"""
        async with self._lock:
            if self._pool:
                return self._pool.pop()
            else:
                # Create new connection if pool exhausted
                logger.warning("database_pool_exhausted", creating_new=True)
                db_url = self.config.DATABASE_URL
                if db_url.startswith('postgresql://'):
                    db_url = db_url.replace('postgresql://', 'postgres://')
                db = DAL(db_url, pool_size=1, migrate=False)
                self._define_tables(db)
                return db

    async def release_connection(self, db: DAL) -> None:
        """Return connection to pool"""
        async with self._lock:
            if len(self._pool) < self._pool_size:
                self._pool.append(db)
            else:
                db.close()

    async def close_all(self) -> None:
        """Close all connections"""
        async with self._lock:
            for db in self._pool:
                try:
                    db.close()
                except Exception as e:
                    logger.error("database_close_error", error=str(e))
            self._pool.clear()
            self._initialized = False
        logger.info("database_connections_closed")


async def init_database(app: Quart) -> None:
    """Initialize database for application"""
    global _db_manager
    _db_manager = DatabaseManager(app.killkrill_config)
    await _db_manager.initialize()
    app.db_manager = _db_manager


async def close_database(app: Quart) -> None:
    """Close database connections"""
    global _db_manager
    if _db_manager:
        await _db_manager.close_all()


async def get_db() -> Optional[DAL]:
    """Get database connection for current request"""
    global _db_manager
    if _db_manager is None:
        return None

    db = _db_context.get()
    if db is None:
        db = await _db_manager.get_connection()
        _db_context.set(db)
    return db


async def release_db() -> None:
    """Release database connection after request"""
    global _db_manager
    db = _db_context.get()
    if db is not None and _db_manager is not None:
        await _db_manager.release_connection(db)
        _db_context.set(None)
