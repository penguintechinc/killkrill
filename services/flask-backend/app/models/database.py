"""
KillKrill Flask Backend - Database Instance

Central db instance for Flask-SQLAlchemy.
Import this to avoid circular dependencies.

Also re-exports PyDAL functions for API blueprints.
"""

from flask_sqlalchemy import SQLAlchemy

# Create db instance for Flask-SQLAlchemy
db = SQLAlchemy()

# Re-export PyDAL functions from db_init for convenience
# This allows blueprints to import from either location
from app.models.db_init import get_engine, get_pydal_connection, get_pydal_db

__all__ = ["db", "get_engine", "get_pydal_connection", "get_pydal_db"]
