# KillKrill Flask Backend

Production-ready Flask application factory with enterprise-grade authentication, monitoring, and observability support.

## Features

- **Flask Application Factory Pattern**: Modular, testable architecture
- **Flask-Security-Too Integration**: User authentication and role-based access control (RBAC)
- **JWT Authentication**: Token-based API authentication with role and permission claims
- **Multi-Method Authentication**: Support for API keys, JWT, and mTLS
- **CORS Configuration**: Flexible cross-origin resource sharing
- **Health Check Endpoint**: `/healthz` for liveness/readiness probes
- **Prometheus Metrics**: `/metrics` endpoint with request metrics collection
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Request Correlation**: All requests traced with unique correlation IDs
- **Error Handling**: Comprehensive error handlers with proper HTTP status codes
- **Role-Based Access Control**: Admin, Maintainer, Viewer roles
- **API v1 Blueprint**: Organized API endpoint structure
- **Database Support**: PostgreSQL, MySQL, SQLite with connection pooling
- **gRPC Support**: Separate gRPC server (port 50051)
- **Production Ready**: Gunicorn, Hypercorn, multi-worker support
- **Type Hints**: Full Python 3.13 type annotation support

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Setup database
export DATABASE_URL="postgresql://user:pass@localhost:5432/killkrill"
export JWT_SECRET="your-secret-key"
```

### Development

```bash
# Run with development server
python main.py --env=development --debug

# Or directly
python -c "from app import create_app; app = create_app('development'); app.run()"
```

### Production

```bash
# Run with Gunicorn (HTTP only)
python main.py --env=production --no-grpc --workers=4

# Run with both HTTP and gRPC
python main.py --env=production --workers=4

# Run gRPC server only
python main.py --env=production --grpc-only
```

## Environment Variables

```bash
# Flask Configuration
FLASK_ENV=development|testing|production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/killkrill
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Authentication
JWT_SECRET=your-secret-key-here
JWT_EXPIRY_HOURS=24

# License Server
LICENSE_KEY=PENG-XXXX-XXXX-XXXX-XXXX-ABCD
LICENSE_SERVER_URL=https://license.penguintech.io
PRODUCT_NAME=killkrill

# Logging
LOG_LEVEL=INFO
ENABLE_DETAILED_METRICS=true

# gRPC
GRPC_PORT=50051

# CORS
CORS_ORIGINS=*

# Workers
WORKERS=4  # 0 = auto-detect CPU count
```

## API Endpoints

### Health & Status

- `GET /healthz` - Health check endpoint
- `GET /metrics` - Prometheus metrics

### Authentication

- `POST /api/v1/auth/login` - Login and get JWT token
- `GET /api/v1/auth/verify` - Verify JWT token
- `POST /api/v1/auth/logout` - Logout

### API v1 Endpoints

- `GET /api/v1/status` - API status
- `GET /api/v1/sources` - List log sources
- `POST /api/v1/sources` - Create source
- `GET /api/v1/sources/<id>` - Get source
- `PUT /api/v1/sources/<id>` - Update source
- `DELETE /api/v1/sources/<id>` - Delete source
- `GET /api/v1/logs` - List logs
- `GET /api/v1/metrics` - List metrics
- `POST /api/v1/metrics/query` - Query metrics

## Authentication

### JWT Token

```bash
# Login
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}'

# Response
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "expires_in": 86400
}

# Use token
curl -X GET http://localhost:5000/api/v1/status \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### API Key

```bash
curl -X GET http://localhost:5000/api/v1/status \
  -H "X-API-Key: your-api-key"
```

### Request Correlation

All requests automatically include correlation IDs:

```bash
curl -X GET http://localhost:5000/healthz \
  -H "X-Correlation-ID: 12345"

# Response includes:
# X-Correlation-ID: 12345
```

## Role-Based Access Control

### Roles

- **admin**: Full access to all resources and operations
- **maintainer**: Can create, update, and delete resources
- **viewer**: Read-only access

### Using Role Decorators

```python
from app import require_role, require_permission
from flask import jsonify

@app.route('/api/v1/admin/config', methods=['PUT'])
@require_role('admin')
def update_admin_config():
    return jsonify({'message': 'Config updated'}), 200

@app.route('/api/v1/logs', methods=['GET'])
@require_role('viewer', 'maintainer', 'admin')
def list_logs():
    return jsonify({'logs': []}), 200

@app.route('/api/v1/sources', methods=['POST'])
@require_permission('write', 'create')
def create_source():
    return jsonify({'message': 'Source created'}), 201
```

## Database Models

### User Model

```python
from app.models.user import User

user = User(
    username='john.doe',
    email='john@example.com',
    password=hash_password('secret'),
    first_name='John',
    last_name='Doe',
    active=True,
    confirmed_at=datetime.utcnow()
)
db.session.add(user)
db.session.commit()
```

### Role Model

```python
from app.models.user import Role

admin_role = Role(
    name='admin',
    description='Administrator role',
    permissions=['read', 'write', 'delete', 'admin']
)
db.session.add(admin_role)
db.session.commit()
```

### API Key Model

```python
from app.models.user import APIKey
import hashlib

api_key = APIKey(
    user_id=user.id,
    key_hash=hashlib.sha256(b'secret-key').hexdigest(),
    name='Integration API Key',
    is_active=True
)
db.session.add(api_key)
db.session.commit()
```

### Audit Log Model

```python
from app.models.user import AuditLog

audit_log = AuditLog(
    user_id=user.id,
    action='UPDATE_SOURCE',
    resource_type='source',
    resource_id='source-123',
    status='success',
    client_ip='192.168.1.1',
    correlation_id=g.correlation_id
)
db.session.add(audit_log)
db.session.commit()
```

## Metrics Collection

Prometheus metrics are collected automatically:

```bash
# Get all metrics
curl http://localhost:5000/metrics

# Output includes:
# killkrill_flask_backend_requests_total{endpoint="/healthz",method="GET",status="200"} 42.0
# killkrill_flask_backend_request_duration_seconds_sum{endpoint="/healthz",method="GET"} 0.123
# killkrill_flask_backend_request_duration_seconds_count{endpoint="/healthz",method="GET"} 42.0
```

## Logging

Structured logs are emitted in JSON format:

```json
{
  "event": "request_completed",
  "timestamp": "2024-12-17T10:30:45.123456Z",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "GET",
  "path": "/api/v1/status",
  "status_code": 200,
  "duration_seconds": 0.023
}
```

### Log Levels

- `-v`: Warnings and critical errors only
- `-vv`: Info level (default)
- `-vvv`: Debug logging

## Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=app tests/

# Integration tests
pytest tests/integration/

# Unit tests
pytest tests/unit/
```

## Error Handling

The application implements comprehensive error handlers:

- **400 Bad Request**: Invalid input or malformed request
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Unhandled application error

All error responses include:

```json
{
  "error": "Error Type",
  "message": "Human-readable error message",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_code": 400
}
```

## File Structure

```
flask-backend/
├── app/
│   ├── __init__.py           # Flask factory and app initialization
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/               # API v1 blueprint
│   │       └── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── db_init.py        # Database initialization
│   │   └── user.py           # User/Role/APIKey models
│   ├── middleware/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   └── grpc/
│       ├── __init__.py
│       ├── protos/           # Protocol Buffer definitions
│       └── services/         # gRPC service implementations
├── main.py                   # Application entry point
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Production Deployment

### Docker

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000 50051

CMD ["python", "main.py", "--env=production", "--workers=4"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: killkrill-flask-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: killkrill-flask-backend
  template:
    metadata:
      labels:
        app: killkrill-flask-backend
    spec:
      containers:
        - name: flask-backend
          image: killkrill:flask-backend-latest
          ports:
            - containerPort: 5000
              name: http
            - containerPort: 50051
              name: grpc
          livenessProbe:
            httpGet:
              path: /healthz
              port: 5000
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /healthz
              port: 5000
            initialDelaySeconds: 5
            periodSeconds: 5
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: killkrill-secrets
                  key: database-url
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: killkrill-secrets
                  key: jwt-secret
```

## License

Limited AGPL3 with preamble for fair use. See LICENSE.md in project root.

## Support

For issues, questions, or contributions, please refer to the main project documentation.
