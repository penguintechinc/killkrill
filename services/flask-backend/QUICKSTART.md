# Flask Backend Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd /home/penguin/code/killkrill/services/flask-backend
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export FLASK_ENV=development
export DATABASE_URL=postgresql://user:pass@localhost:5432/killkrill
export JWT_SECRET=dev-secret-key-change-in-production
export FLASK_PORT=5000
```

### 3. Run Development Server

```bash
python main.py --debug
```

Server will start on `http://localhost:5000`

## Testing the API

### Health Check

```bash
curl http://localhost:5000/healthz
```

### Get Metrics

```bash
curl http://localhost:5000/metrics
```

### Login (Get JWT Token)

```bash
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'
```

Response:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

### Use Token to Call Protected Endpoint

```bash
curl -X GET http://localhost:5000/api/v1/status \
  -H "Authorization: Bearer <TOKEN_FROM_ABOVE>"
```

## Project Structure

```
flask-backend/
├── app/
│   ├── __init__.py           # Main app factory
│   ├── api/
│   │   └── v1/               # API endpoints
│   ├── models/
│   │   ├── user.py           # Database models
│   │   └── db_init.py        # Database setup
│   ├── middleware/           # Request middleware
│   ├── services/             # Business logic
│   └── grpc/                 # gRPC services
├── main.py                   # Entry point
├── requirements.txt          # Dependencies
├── README.md                 # Full documentation
└── IMPLEMENTATION.md         # Implementation details
```

## Key Features

### Authentication

- JWT tokens with automatic expiration
- API keys for programmatic access
- Role-based access control (admin, maintainer, viewer)

### Monitoring

- Health check endpoint: `/healthz`
- Prometheus metrics: `/metrics`
- Request tracing with correlation IDs
- Structured JSON logging

### Database Support

- PostgreSQL (default)
- MySQL/MariaDB
- SQLite (development)

## Common Commands

### Development

```bash
# Run with debug
python main.py --debug

# Run with custom port
python main.py --port 8000

# Run with custom workers
python main.py --workers 8
```

### Production

```bash
# HTTP only
python main.py --env=production --no-grpc

# HTTP + gRPC
python main.py --env=production

# gRPC only
python main.py --env=production --grpc-only
```

### Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=app tests/

# Specific test
pytest tests/test_api.py::test_login
```

## Environment Variables Reference

| Variable         | Default     | Description                                   |
| ---------------- | ----------- | --------------------------------------------- |
| FLASK_ENV        | development | Environment: development, testing, production |
| FLASK_HOST       | 0.0.0.0     | HTTP server host                              |
| FLASK_PORT       | 5000        | HTTP server port                              |
| GRPC_PORT        | 50051       | gRPC server port                              |
| DATABASE_URL     | -           | Database connection string                    |
| JWT_SECRET       | -           | JWT signing secret                            |
| JWT_EXPIRY_HOURS | 24          | JWT token expiration                          |
| WORKERS          | 4           | Number of Gunicorn workers (0 = auto)         |
| LOG_LEVEL        | INFO        | Logging level                                 |
| CORS_ORIGINS     | \*          | Comma-separated allowed origins               |

## Troubleshooting

### Database Connection Error

```bash
# Check DATABASE_URL is set correctly
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Port Already in Use

```bash
# Use different port
python main.py --port 8001

# Or kill process using port
lsof -i :5000
kill -9 <PID>
```

### Import Errors

```bash
# Ensure we're in correct directory
cd /home/penguin/code/killkrill/services/flask-backend

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### JWT Token Expired

Tokens expire after 24 hours (default). Get a new token:

```bash
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'
```

## API Endpoints Cheat Sheet

| Method | Endpoint              | Description   | Auth Required |
| ------ | --------------------- | ------------- | ------------- |
| POST   | /api/v1/auth/login    | Get JWT token | No            |
| GET    | /api/v1/auth/verify   | Verify token  | Yes           |
| POST   | /api/v1/auth/logout   | Logout        | Yes           |
| GET    | /api/v1/status        | API status    | No            |
| GET    | /api/v1/sources       | List sources  | Yes           |
| POST   | /api/v1/sources       | Create source | Yes           |
| GET    | /api/v1/sources/{id}  | Get source    | Yes           |
| PUT    | /api/v1/sources/{id}  | Update source | Yes           |
| DELETE | /api/v1/sources/{id}  | Delete source | Yes           |
| GET    | /api/v1/logs          | List logs     | Yes           |
| GET    | /api/v1/metrics       | List metrics  | Yes           |
| POST   | /api/v1/metrics/query | Query metrics | Yes           |

## Docker Quick Start

### Build Image

```bash
docker build -t killkrill-backend:latest .
```

### Run Container

```bash
docker run -p 5000:5000 -p 50051:50051 \
  -e DATABASE_URL=postgresql://user:pass@db:5432/killkrill \
  -e JWT_SECRET=secret-key \
  killkrill-backend:latest
```

## Next Steps

1. **Read Full Documentation**: See `README.md` for comprehensive guide
2. **Understand Architecture**: See `IMPLEMENTATION.md` for technical details
3. **Configure Database**: Set up PostgreSQL connection
4. **Implement Services**: Add business logic in `app/services/`
5. **Add Tests**: Create unit and integration tests
6. **Deploy**: Use Docker or Kubernetes manifests

## Support & Help

- Check `README.md` for detailed documentation
- See `IMPLEMENTATION.md` for technical architecture
- Review error messages and correlation IDs in logs
- All errors include correlation ID for tracing

## License

Limited AGPL3 with preamble for fair use.
