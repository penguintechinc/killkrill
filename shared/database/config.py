"""
Database configuration module.

Handles parsing of DATABASE_URL or individual DB_* environment variables.
Supports PostgreSQL, MySQL/MariaDB, and SQLite.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

VALID_DB_TYPES = {"postgres", "mysql", "sqlite"}


@dataclass(slots=True, frozen=True)
class DatabaseConfig:
    """Database configuration with validation."""

    db_type: str
    host: Optional[str]
    port: Optional[int]
    name: str
    user: Optional[str]
    password: Optional[str]
    pool_size: int
    galera_mode: bool

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Parse database configuration from environment variables."""
        database_url = os.getenv("DATABASE_URL")

        if database_url:
            return cls._from_url(database_url)
        else:
            return cls._from_individual_vars()

    @classmethod
    def _from_url(cls, url: str) -> "DatabaseConfig":
        """Parse DATABASE_URL into configuration."""
        parsed = urlparse(url)

        # Map URL scheme to db_type
        scheme_map = {
            "postgresql": "postgres",
            "postgres": "postgres",
            "mysql": "mysql",
            "mariadb": "mysql",
            "sqlite": "sqlite",
        }

        db_type = scheme_map.get(parsed.scheme)
        if not db_type:
            raise ValueError(f"Unsupported database scheme: {parsed.scheme}")

        if db_type == "sqlite":
            # SQLite: path is database name
            name = parsed.path.lstrip("/")
            return cls(
                db_type="sqlite",
                host=None,
                port=None,
                name=name or "killkrill.db",
                user=None,
                password=None,
                pool_size=1,
                galera_mode=False,
            )
        else:
            # PostgreSQL/MySQL
            pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
            galera_mode = os.getenv("GALERA_MODE", "false").lower() == "true"

            return cls(
                db_type=db_type,
                host=parsed.hostname or "localhost",
                port=parsed.port or cls._default_port(db_type),
                name=parsed.path.lstrip("/") or "killkrill",
                user=parsed.username,
                password=parsed.password,
                pool_size=pool_size,
                galera_mode=galera_mode,
            )

    @classmethod
    def _from_individual_vars(cls) -> "DatabaseConfig":
        """Parse individual DB_* environment variables."""
        db_type = os.getenv("DB_TYPE", "postgres")

        if db_type not in VALID_DB_TYPES:
            raise ValueError(
                f"Invalid DB_TYPE: {db_type}. " f"Must be one of: {VALID_DB_TYPES}"
            )

        if db_type == "sqlite":
            name = os.getenv("DB_NAME", "killkrill.db")
            return cls(
                db_type="sqlite",
                host=None,
                port=None,
                name=name,
                user=None,
                password=None,
                pool_size=1,
                galera_mode=False,
            )
        else:
            pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
            galera_mode = os.getenv("GALERA_MODE", "false").lower() == "true"

            return cls(
                db_type=db_type,
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", str(cls._default_port(db_type)))),
                name=os.getenv("DB_NAME", "killkrill"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                pool_size=pool_size,
                galera_mode=galera_mode,
            )

    @staticmethod
    def _default_port(db_type: str) -> int:
        """Get default port for database type."""
        return {
            "postgres": 5432,
            "mysql": 3306,
        }.get(db_type, 5432)

    def to_sqlalchemy_url(self) -> str:
        """Generate SQLAlchemy connection URL."""
        if self.db_type == "sqlite":
            return f"sqlite:///{self.name}"
        elif self.db_type == "postgres":
            return (
                f"postgresql://{self.user}:{self.password}@"
                f"{self.host}:{self.port}/{self.name}"
            )
        elif self.db_type == "mysql":
            return (
                f"mysql+pymysql://{self.user}:{self.password}@"
                f"{self.host}:{self.port}/{self.name}"
            )
        else:
            raise ValueError(f"Unsupported db_type: {self.db_type}")

    def to_pydal_uri(self) -> str:
        """Generate PyDAL connection URI."""
        if self.db_type == "sqlite":
            return f"sqlite://{self.name}"
        elif self.db_type == "postgres":
            return (
                f"postgres://{self.user}:{self.password}@"
                f"{self.host}:{self.port}/{self.name}"
            )
        elif self.db_type == "mysql":
            return (
                f"mysql://{self.user}:{self.password}@"
                f"{self.host}:{self.port}/{self.name}"
            )
        else:
            raise ValueError(f"Unsupported db_type: {self.db_type}")

    def get_pydal_kwargs(self) -> Dict[str, Any]:
        """Get PyDAL connection keyword arguments."""
        kwargs = {
            "pool_size": self.pool_size,
            "migrate_enabled": True,
            "check_reserved": ["all"],
            "lazy_tables": True,
            "folder": os.getenv("MIGRATION_FOLDER", "/tmp/killkrill-migrations/"),
        }

        # MariaDB Galera specific settings
        if self.galera_mode and self.db_type == "mysql":
            kwargs["driver_args"] = {"init_command": "SET wsrep_sync_wait=1"}

        return kwargs

    def get_sqlalchemy_kwargs(self) -> Dict[str, Any]:
        """Get SQLAlchemy engine keyword arguments."""
        if self.db_type == "sqlite":
            return {
                "poolclass": None,  # Use NullPool for SQLite
                "connect_args": {"check_same_thread": False},
            }
        else:
            kwargs = {
                "pool_size": self.pool_size,
                "max_overflow": self.pool_size * 2,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }

            # MariaDB Galera specific settings
            if self.galera_mode and self.db_type == "mysql":
                kwargs["connect_args"] = {"init_command": "SET wsrep_sync_wait=1"}

            return kwargs
