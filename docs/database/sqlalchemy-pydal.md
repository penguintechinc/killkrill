# SQLAlchemy and PyDAL Hybrid Database Approach

## Overview

Killkrill uses a hybrid database strategy that separates concerns between database initialization and runtime operations:

- **SQLAlchemy**: Schema design, migrations, complex initialization operations
- **PyDAL**: Day-to-day CRUD operations, multi-database abstraction, simple query syntax

This approach balances SQLAlchemy's robust schema versioning with PyDAL's simplicity and database portability.

## Architecture

```
Application Startup
    ↓
┌───────────────────────────────┐
│ SQLAlchemy Phase              │
│ - Schema initialization       │
│ - Database migrations         │
│ - Complex setup operations    │
│ - Connection pool creation    │
└───────────────────────────────┘
    ↓
Runtime Operations
    ↓
┌───────────────────────────────┐
│ PyDAL Phase                   │
│ - CRUD operations             │
│ - Simple queries              │
│ - Multi-database support      │
│ - Request-scoped connections  │
└───────────────────────────────┘
```

## SQLAlchemy: Initialization Phase

### Schema Definition with SQLAlchemy

Use SQLAlchemy's declarative approach for robust schema definition:

```python
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    """User model for SQLAlchemy schema definition"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    logs = relationship('LogEntry', back_populates='user')

class LogEntry(Base):
    """Log entry model"""
    __tablename__ = 'log_entries'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(String(1000), nullable=False)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship
    user = relationship('User', back_populates='logs')

class Metric(Base):
    """Metric model for time-series data"""
    __tablename__ = 'metrics'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    value = Column(Float, nullable=False)
    tags = Column(String(500))  # JSON string for flexibility
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
```

### Database Initialization with SQLAlchemy

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

def initialize_database():
    """Initialize database schema using SQLAlchemy"""
    # Get database URL from environment
    db_url = build_database_url()

    # Create engine with connection pooling
    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        echo=os.getenv('DB_ECHO', 'false').lower() == 'true'
    )

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return engine, SessionLocal

def build_database_url():
    """Build database URL from environment variables"""
    db_type = os.getenv('DB_TYPE', 'postgres')
    db_user = os.getenv('DB_USER', 'postgres')
    db_pass = os.getenv('DB_PASS', '')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'killkrill')

    if db_type == 'sqlite':
        return f"sqlite:///{db_name}.db"
    elif db_type == 'mysql':
        return f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    else:  # postgres
        return f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

# Called during application startup
engine, SessionLocal = initialize_database()
```

### Alembic Migrations

Alembic provides version control for schema changes:

```bash
# Initialize Alembic in project
alembic init alembic

# Create initial migration from existing models
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

**migration_env.py configuration:**

```python
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig
from app.database.models import Base

config = context.config

# Load SQLAlchemy URL from environment
config.set_main_option("sqlalchemy.url", build_database_url())

fileConfig(config.config_file_name)

# Point to model metadata
target_metadata = Base.metadata

# Auto-generate migrations
context.configure(
    connection=engine.connect(),
    target_metadata=target_metadata,
    render_as_batch=True,  # For SQLite compatibility
)
```

## PyDAL: Runtime Operations Phase

### PyDAL Table Definitions

Define PyDAL tables that mirror SQLAlchemy schema:

```python
from pydal import DAL, Field
import os

class Database:
    """Database access layer using PyDAL for runtime operations"""

    def __init__(self):
        self.db = None
        self.initialize()

    def initialize(self):
        """Initialize PyDAL connection"""
        db_url = build_database_url()

        self.db = DAL(
            db_url,
            pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
            migrate_enabled=True,
            lazy_tables=True
        )

        # Define tables matching SQLAlchemy schema
        self._define_tables()

    def _define_tables(self):
        """Define PyDAL tables for runtime operations"""
        db = self.db

        # Users table
        db.define_table('users',
            Field('email', 'string', unique=True, notnull=True),
            Field('password', 'string', notnull=True),
            Field('full_name', 'string'),
            Field('active', 'boolean', default=True),
            Field('created_at', 'datetime'),
            Field('updated_at', 'datetime'),
            migrate=True
        )

        # Log entries table
        db.define_table('log_entries',
            Field('user_id', 'reference users'),
            Field('message', 'string', notnull=True),
            Field('level', 'string', notnull=True),  # INFO, WARNING, ERROR
            Field('created_at', 'datetime', notnull=True),
            migrate=True
        )

        # Metrics table
        db.define_table('metrics',
            Field('name', 'string', notnull=True),
            Field('value', 'double'),
            Field('tags', 'string'),  # JSON
            Field('timestamp', 'datetime', notnull=True),
            migrate=True
        )

    def get_db(self):
        """Return database instance for queries"""
        return self.db

# Global database instance
db_instance = Database()
```

### CRUD Operations with PyDAL

```python
from quart import Quart, jsonify, request
from dataclasses import dataclass
from typing import Optional, List

app = Quart(__name__)

@dataclass(slots=True)
class UserData:
    """User data model with slots for memory efficiency"""
    id: int
    email: str
    full_name: Optional[str]
    active: bool

# CREATE
@app.route('/api/v1/users', methods=['POST'])
async def create_user():
    data = await request.get_json()

    db = db_instance.get_db()
    user_id = db.users.insert(
        email=data['email'],
        password=hash_password(data['password']),
        full_name=data.get('full_name'),
        active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    return jsonify({'id': user_id, 'email': data['email']}), 201

# READ
@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
async def get_user(user_id):
    db = db_instance.get_db()

    row = db.users[user_id]
    if not row:
        return jsonify({'error': 'User not found'}), 404

    user = UserData(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        active=row.active
    )

    return jsonify({'user': user.__dict__}), 200

# READ multiple with filtering
@app.route('/api/v1/users', methods=['GET'])
async def list_users():
    db = db_instance.get_db()

    active = request.args.get('active', 'true').lower() == 'true'
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    rows = db(db.users.active == active).select(
        limitby=(offset, offset + limit)
    )

    users = [
        UserData(
            id=r.id,
            email=r.email,
            full_name=r.full_name,
            active=r.active
        )
        for r in rows
    ]

    return jsonify({'users': [u.__dict__ for u in users]}), 200

# UPDATE
@app.route('/api/v1/users/<int:user_id>', methods=['PUT'])
async def update_user(user_id):
    data = await request.get_json()

    db = db_instance.get_db()

    db(db.users.id == user_id).update(
        full_name=data.get('full_name'),
        updated_at=datetime.utcnow()
    )

    return jsonify({'updated': True}), 200

# DELETE
@app.route('/api/v1/users/<int:user_id>', methods=['DELETE'])
async def delete_user(user_id):
    db = db_instance.get_db()

    db(db.users.id == user_id).delete()

    return '', 204
```

### Complex Queries with PyDAL

```python
from datetime import datetime, timedelta

def get_user_recent_logs(user_id: int, days: int = 7) -> List[dict]:
    """Get user's logs from past N days"""
    db = db_instance.get_db()

    cutoff = datetime.utcnow() - timedelta(days=days)

    logs = db(
        (db.log_entries.user_id == user_id) &
        (db.log_entries.created_at >= cutoff)
    ).select(
        orderby=~db.log_entries.created_at  # Descending
    )

    return [
        {
            'id': log.id,
            'message': log.message,
            'level': log.level,
            'created_at': log.created_at.isoformat()
        }
        for log in logs
    ]

def get_metrics_summary(metric_name: str, hours: int = 24) -> dict:
    """Get metrics summary for past N hours"""
    db = db_instance.get_db()

    cutoff = datetime.utcnow() - timedelta(hours=hours)

    metrics = db(
        (db.metrics.name == metric_name) &
        (db.metrics.timestamp >= cutoff)
    ).select()

    if not metrics:
        return {'count': 0}

    values = [m.value for m in metrics if m.value is not None]

    return {
        'count': len(values),
        'min': min(values),
        'max': max(values),
        'avg': sum(values) / len(values)
    }
```

## Multi-Database Support

### Environment Configuration

```bash
# PostgreSQL (default)
DB_TYPE=postgres
DB_USER=postgres
DB_PASS=password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=killkrill

# MySQL/MariaDB
DB_TYPE=mysql
DB_USER=root
DB_PASS=password
DB_HOST=mysql-server
DB_PORT=3306
DB_NAME=killkrill

# SQLite (development)
DB_TYPE=sqlite
DB_NAME=killkrill.db
```

### Database URL Builder

```python
def build_database_url():
    """Build database URL from environment variables"""
    db_type = os.getenv('DB_TYPE', 'postgres')

    if db_type == 'sqlite':
        db_name = os.getenv('DB_NAME', 'killkrill.db')
        return f"sqlite:///{db_name}"

    if db_type == 'mysql':
        user = os.getenv('DB_USER', 'root')
        password = os.getenv('DB_PASS', '')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '3306')
        name = os.getenv('DB_NAME', 'killkrill')
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"

    # PostgreSQL (default)
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASS', '')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    name = os.getenv('DB_NAME', 'killkrill')
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"
```

## Migration Workflow

### Typical Development Cycle

```
1. Modify SQLAlchemy models (app/database/models.py)
        ↓
2. Generate Alembic migration:
   alembic revision --autogenerate -m "Description"
        ↓
3. Review and adjust migration (alembic/versions/)
        ↓
4. Apply migration to development database:
   alembic upgrade head
        ↓
5. Update PyDAL table definitions (app/database.py)
        ↓
6. Update API endpoints to use new fields
        ↓
7. Test thoroughly in development
        ↓
8. Commit schema changes with migration files
```

### Production Migration Process

```bash
# Backup database before migration
pg_dump -U postgres killkrill > backup.sql

# Apply pending migrations
alembic upgrade head

# If issues occur, rollback
alembic downgrade -1
psql -U postgres killkrill < backup.sql
```

## Best Practices

### Separation of Concerns

- **SQLAlchemy schema**: Source of truth for database structure
- **Alembic migrations**: Version control for schema changes
- **PyDAL operations**: All runtime queries and business logic
- **Application code**: Use dataclasses for type safety and memory efficiency

### Connection Management

```python
# Use context managers for automatic cleanup
async with db_instance.get_db() as db:
    users = db.users.select()

# Or use request-scoped connections
@app.before_request
async def setup_db():
    g.db = db_instance.get_db()

@app.after_request
async def teardown_db(response):
    if hasattr(g, 'db'):
        g.db.close()
    return response
```

### Performance Optimization

- Use connection pooling (configured in PyDAL)
- Create indexes on frequently queried columns
- Use `lazy_tables=True` in PyDAL for on-demand table loading
- Use dataclasses with slots for memory efficiency
- Paginate large result sets with LIMIT/OFFSET

### Testing Strategy

```python
# Use in-memory SQLite for tests
@pytest.fixture
def test_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

# Test both SQLAlchemy and PyDAL layers
@pytest.mark.asyncio
async def test_user_creation(test_db):
    # SQLAlchemy: Verify schema
    assert 'users' in [t.name for t in Base.metadata.sorted_tables]

    # PyDAL: Test runtime operation
    db = DAL('sqlite:///:memory:')
    db.define_table('users',
        Field('email', 'string'),
        Field('active', 'boolean')
    )
    user_id = db.users.insert(email='test@example.com', active=True)
    assert user_id > 0
```

## Troubleshooting

**Issue**: Alembic fails to auto-detect changes
**Solution**: Explicitly add/remove operations in migration file or use `alembic revision -m "..."` for manual migrations

**Issue**: PyDAL migrations interfere with Alembic
**Solution**: Set `migrate=False` in PyDAL table definitions for production

**Issue**: Database locked errors with SQLite
**Solution**: Use PostgreSQL for production, SQLite only for local development

**Issue**: Connection pool exhaustion
**Solution**: Increase `pool_size` and `max_overflow` in SQLAlchemy engine configuration
