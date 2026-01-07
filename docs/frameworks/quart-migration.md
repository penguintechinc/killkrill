# Quart Migration Guide: From Flask/py4web to Quart

## Overview

This guide covers migrating Flask and py4web applications to Quart, an async-compatible ASGI framework that maintains API compatibility with Flask while enabling async/await patterns for high-performance I/O operations.

## Route Conversion

### Flask to Quart Route Patterns

**Flask-style routes remain compatible in Quart:**

```python
from quart import Quart, jsonify, request

app = Quart(__name__)

# Simple GET route - works identically
@app.route('/api/v1/health', methods=['GET'])
async def health_check():
    return jsonify({'status': 'healthy'}), 200

# Route with parameters
@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
async def get_user(user_id):
    return jsonify({'id': user_id}), 200

# POST with JSON body
@app.route('/api/v1/users', methods=['POST'])
async def create_user():
    data = await request.get_json()
    return jsonify({'created': True, 'data': data}), 201
```

**Key differences from Flask:**
- All route handlers must be `async def` (though Quart supports sync functions)
- Request body access requires `await` (e.g., `await request.get_json()`)
- Return values identical to Flask
- Blueprint patterns remain unchanged

### Blueprint Patterns

Blueprints work identically in Quart, enabling modular service design:

```python
from quart import Blueprint

users_bp = Blueprint('users', __name__, url_prefix='/api/v1/users')

@users_bp.route('', methods=['GET'])
async def list_users():
    # Database query here
    return jsonify({'users': []}), 200

@users_bp.route('/<int:user_id>', methods=['DELETE'])
async def delete_user(user_id):
    # Delete operation
    return '', 204

# Register in main app
app.register_blueprint(users_bp)
```

**Best practices:**
- Organize by resource type (users, logs, metrics)
- One blueprint per service domain
- Maintain consistent URL prefix versioning (`/api/v1/...`)

## Async Request Handling

### Reading Request Data

All request operations must use `await`:

```python
@app.route('/api/v1/logs', methods=['POST'])
async def ingest_logs():
    # Parse JSON body
    logs = await request.get_json()

    # Access form data
    form_data = await request.form

    # Read raw body
    body = await request.get_data()

    # Access query parameters (no await needed)
    limit = request.args.get('limit', 10, type=int)

    return jsonify({'received': len(logs)}), 202
```

### Response Handling

Responses can be async-aware using streaming:

```python
async def generate_metrics():
    """Generator for streaming responses"""
    for i in range(1000):
        yield f"metric_{i},value={i}\n"
        await asyncio.sleep(0.01)  # Simulate processing

@app.route('/api/v1/metrics/stream', methods=['GET'])
async def stream_metrics():
    return generate_metrics(), 200, {
        'Content-Type': 'text/plain',
        'Transfer-Encoding': 'chunked'
    }
```

### Error Handling with Async

Use Quart's error handlers with async support:

```python
@app.errorhandler(404)
async def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
async def internal_error(error):
    # Async logging/cleanup
    await log_error(error)
    return jsonify({'error': 'Internal server error'}), 500
```

## Flask-Security-Too Integration

Flask-Security-Too works with Quart without modification:

```python
from flask_security import Security, SQLAlchemyUserDatastore, auth_required
from quart import Quart

app = Quart(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Standard Flask-Security-Too setup
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

# Routes with @auth_required decorator work in Quart
@app.route('/api/v1/protected', methods=['GET'])
@auth_required()
async def protected_endpoint():
    return jsonify({'authenticated': True}), 200
```

## Middleware and Context Handling

### Custom Middleware in Quart

```python
@app.before_request
async def before_request():
    # Async operations allowed
    g.db = await get_db_connection()

@app.after_request
async def after_request(response):
    # Cleanup
    if hasattr(g, 'db'):
        await g.db.close()
    return response
```

### Application Context

Quart maintains Flask's application/request context:

```python
@app.route('/api/v1/example', methods=['GET'])
async def example():
    from flask import current_app, g

    # Access config
    debug_mode = current_app.config['DEBUG']

    # Use g for request-scoped data
    g.user_id = current_user.id

    return jsonify({'ok': True}), 200
```

## Configuration and Initialization

### Environment Variables

```python
import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    QUART_ENV = os.getenv('QUART_ENV', 'development')
    DB_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')

app.config.from_object(Config)
```

### Application Factory Pattern

```python
def create_app(config=None):
    app = Quart(__name__)

    if config:
        app.config.from_object(config)
    else:
        app.config.from_object('config.Config')

    # Initialize extensions
    init_database(app)
    init_security(app)
    init_blueprints(app)

    return app

# Usage
app = create_app()
```

## Deployment

### Docker Configuration

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["quart", "run", "--host", "0.0.0.0", "--port", "5000"]
```

### Uvicorn/ASGI

Quart works with any ASGI server:

```bash
# Development
quart run

# Production with Uvicorn
uvicorn app:app --host 0.0.0.0 --port 5000 --workers 4

# Production with Hypercorn
hypercorn app:app --bind 0.0.0.0:5000 --workers 4
```

## Migration Checklist

- [ ] Replace `from flask import Flask` with `from quart import Quart`
- [ ] Convert all route handlers to `async def`
- [ ] Add `await` to all request body operations (`get_json()`, `form`, etc.)
- [ ] Update tests to use `pytest-quart` or `pytest-asyncio`
- [ ] Test with actual ASGI server (Uvicorn/Hypercorn), not development server
- [ ] Verify Flask extensions compatibility (check Quart docs)
- [ ] Update CI/CD for ASGI server deployment
- [ ] Load test with async-aware tools

## Performance Considerations

- Quart enables concurrent request handling via async/await
- Use connection pooling for database access (critical for throughput)
- Avoid blocking operations in async context (CPU-bound work use `asyncio.to_thread()`)
- Monitor event loop for blocking calls (use `asyncio` profiling)

## Common Pitfalls and Solutions

**Issue**: Using sync libraries in async routes
**Solution**: Wrap blocking operations with `asyncio.to_thread()` or use async variants

**Issue**: Missing `await` on async operations
**Solution**: Static analysis tools and type hints catch these (enable mypy strict mode)

**Issue**: Database connections not properly async
**Solution**: Use async SQLAlchemy or PyDAL with connection pooling

**Issue**: Request context lost in async operations
**Solution**: Use Quart's `copy_current_request_context()` decorator

## References

- [Quart Documentation](https://quart.palletsprojects.com/)
- [AsyncIO Best Practices](https://docs.python.org/3/library/asyncio.html)
- [ASGI Specification](https://asgi.readthedocs.io/)
