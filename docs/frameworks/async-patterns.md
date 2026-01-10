# Async/Await Patterns and Best Practices

## Core Async Patterns

### Pattern 1: Concurrent Request Handling

**Use async routes to handle multiple requests concurrently:**

```python
import asyncio
from quart import Quart, jsonify, request

app = Quart(__name__)

@app.route('/api/v1/process', methods=['POST'])
async def process_data():
    # Multiple async operations execute concurrently
    data = await request.get_json()

    # Run tasks in parallel
    results = await asyncio.gather(
        validate_data(data),
        enrich_data(data),
        check_permissions(data)
    )

    return jsonify({'success': True, 'results': results}), 200

async def validate_data(data):
    # Async validation
    await asyncio.sleep(0.1)
    return {'valid': True}

async def enrich_data(data):
    # Async enrichment
    await asyncio.sleep(0.05)
    return {'enriched': True}

async def check_permissions(data):
    # Async permission check
    await asyncio.sleep(0.02)
    return {'authorized': True}
```

### Pattern 2: Sequential vs Parallel Operations

```python
# Bad: Sequential (slow)
async def bad_workflow(user_id):
    user = await get_user(user_id)
    logs = await get_user_logs(user_id)  # Waits for user lookup
    metrics = await get_user_metrics(user_id)  # Waits for logs
    return {'user': user, 'logs': logs, 'metrics': metrics}

# Good: Parallel (fast)
async def good_workflow(user_id):
    user, logs, metrics = await asyncio.gather(
        get_user(user_id),
        get_user_logs(user_id),
        get_user_metrics(user_id)
    )
    return {'user': user, 'logs': logs, 'metrics': metrics}
```

### Pattern 3: Database Operations

**Async database access with PyDAL and connection pooling:**

```python
from pydal import DAL, Field
import asyncio

class AsyncDatabasePool:
    def __init__(self, db_url, pool_size=10):
        self.pool = [DAL(db_url) for _ in range(pool_size)]
        self.semaphore = asyncio.Semaphore(pool_size)
        self.index = 0

    async def get_connection(self):
        async with self.semaphore:
            conn = self.pool[self.index % len(self.pool)]
            self.index += 1
            return conn

    async def query(self, table_name, **filters):
        db = await self.get_connection()
        table = db[table_name]
        rows = table(**filters).select()
        return rows

# Usage in routes
db_pool = AsyncDatabasePool(os.getenv('DATABASE_URL'))

@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
async def get_user(user_id):
    rows = await db_pool.query('users', id=user_id)
    return jsonify({'user': rows[0].as_dict() if rows else None}), 200
```

### Pattern 4: Timeout Handling

```python
import asyncio

@app.route('/api/v1/slow-operation', methods=['POST'])
async def slow_operation():
    try:
        # Timeout after 30 seconds
        result = await asyncio.wait_for(
            long_running_task(),
            timeout=30.0
        )
        return jsonify({'result': result}), 200
    except asyncio.TimeoutError:
        return jsonify({'error': 'Operation timed out'}), 408

async def long_running_task():
    await asyncio.sleep(5)
    return {'data': 'processed'}
```

### Pattern 5: Error Handling in Concurrent Operations

```python
async def process_batch(items):
    """Process items with error handling"""
    results = []
    errors = []

    # Process all items, collecting errors
    tasks = [process_item(item) for item in items]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Separate results and errors
    for item, response in zip(items, responses):
        if isinstance(response, Exception):
            errors.append({'item': item, 'error': str(response)})
        else:
            results.append(response)

    return {'success': results, 'failed': errors}

async def process_item(item):
    # May raise exception
    if item.get('invalid'):
        raise ValueError('Invalid item')
    return {'processed': True}
```

## Async Context Managers

### Pattern 6: Resource Management

```python
from contextlib import asynccontextmanager

class DatabaseConnection:
    def __init__(self, url):
        self.url = url
        self.conn = None

    async def __aenter__(self):
        self.conn = DAL(self.url)
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        if self.conn:
            await self.conn.close()

@app.route('/api/v1/data', methods=['GET'])
async def get_data():
    async with DatabaseConnection(os.getenv('DATABASE_URL')) as db:
        rows = db.users.select()
        return jsonify({'users': rows}), 200
```

### Pattern 7: Async Generators

```python
async def stream_logs(query):
    """Async generator for streaming results"""
    db = await get_db_connection()

    logs = db.logs(**query).select()
    for log in logs:
        yield f"{log.timestamp},{log.level},{log.message}\n"
        await asyncio.sleep(0.01)  # Rate limiting

@app.route('/api/v1/logs/stream', methods=['GET'])
async def stream_logs_endpoint():
    query = {'level': request.args.get('level', 'INFO')}
    return stream_logs(query), 200, {'Content-Type': 'text/plain'}
```

## Common Pitfalls

### Pitfall 1: Blocking I/O in Async Context

**Problem**: Synchronous operations block entire event loop

```python
# BAD: Blocks event loop
@app.route('/api/v1/bad', methods=['GET'])
async def bad_endpoint():
    time.sleep(1)  # Blocks everything!
    return jsonify({'ok': True}), 200

# GOOD: Uses asyncio.sleep
@app.route('/api/v1/good', methods=['GET'])
async def good_endpoint():
    await asyncio.sleep(1)  # Yields control
    return jsonify({'ok': True}), 200

# GOOD: Offload CPU work
@app.route('/api/v1/cpu-work', methods=['GET'])
async def cpu_work():
    result = await asyncio.to_thread(cpu_intensive_function)
    return jsonify({'result': result}), 200
```

### Pitfall 2: Missing Await

**Problem**: Forgetting `await` on async operations creates silent bugs

```python
# BAD: Creates coroutine but doesn't execute
@app.route('/api/v1/bad', methods=['GET'])
async def bad_endpoint():
    result = get_user(123)  # Returns coroutine, not user!
    return jsonify({'user': result}), 200

# GOOD: Proper await
@app.route('/api/v1/good', methods=['GET'])
async def good_endpoint():
    result = await get_user(123)  # Executes and returns user
    return jsonify({'user': result}), 200
```

### Pitfall 3: Event Loop Issues

**Problem**: Creating new event loops in async context

```python
# BAD: Creates nested event loop
async def bad_operation():
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(fetch_data())
    return result

# GOOD: Use asyncio.gather for concurrent operations
async def good_operation():
    results = await asyncio.gather(
        fetch_data(),
        fetch_more_data()
    )
    return results
```

### Pitfall 4: Exception Handling in gather()

```python
# Problem: One failure cancels all
async def bad_gather():
    try:
        results = await asyncio.gather(
            task1(),
            task2(),
            task3()
        )
    except Exception:
        # task2 failure cancels task3
        pass

# Solution: Capture exceptions per task
async def good_gather():
    results = await asyncio.gather(
        task1(),
        task2(),
        task3(),
        return_exceptions=True  # Prevents cancellation
    )
    # Process results, checking for Exception types
    processed = [
        r for r in results
        if not isinstance(r, Exception)
    ]
```

### Pitfall 5: Resource Leaks

**Problem**: Forgetting to close async resources

```python
# BAD: Connection leak
@app.route('/api/v1/leak', methods=['GET'])
async def leak():
    db = DAL(os.getenv('DATABASE_URL'))
    return jsonify({'data': db.users.select()}), 200
    # db.close() never called!

# GOOD: Use context manager
@app.route('/api/v1/good', methods=['GET'])
async def no_leak():
    async with get_db_connection() as db:
        return jsonify({'data': db.users.select()}), 200
    # Automatic cleanup
```

## Testing Async Code

### Using pytest-asyncio

```python
import pytest
from quart import Quart

@pytest.fixture
def app():
    app = Quart(__name__)
    yield app

@pytest.mark.asyncio
async def test_async_endpoint(app):
    client = app.test_client()
    response = await client.get('/api/v1/health')
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_concurrent_operations():
    results = await asyncio.gather(
        async_operation_1(),
        async_operation_2(),
        async_operation_3()
    )
    assert len(results) == 3
```

## Performance Monitoring

### Detecting Event Loop Blocking

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

async def monitor_event_loop():
    """Detect slow operations in event loop"""
    loop = asyncio.get_event_loop()

    # Set slow callback duration (seconds)
    if hasattr(loop, 'slow_callback_duration'):
        loop.slow_callback_duration = 0.1

        def log_slow_callback(handle, delay):
            logger.warning(f"Event loop blocked for {delay:.2f}s")

        loop.set_debug(True)
```

## Best Practices Summary

- Use `asyncio.gather()` for parallel operations
- Use `asyncio.wait_for()` for timeouts
- Always `await` async function calls
- Use context managers for resource cleanup
- Test with `pytest-asyncio`
- Monitor event loop blocking with logging
- Offload CPU work to threads with `asyncio.to_thread()`
- Avoid mixing sync and async code
- Use type hints for async functions (`async def func() -> Type:`)
