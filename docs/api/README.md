# KillKrill API Documentation

## Overview

KillKrill provides multiple APIs for log and metrics ingestion, similar to AWS CloudWatch APIs or Google Cloud Operations APIs.

## Data Flow Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Applications  │───▶│ killkrill-      │───▶│ Redis Streams   │───▶│ killkrill-      │
│                 │    │ receiver        │    │                 │    │ processor       │
│ - HTTP3/QUIC    │    │                 │    │ - logs:raw      │    │                 │
│ - UDP Syslog    │    │ - XDP filtering │    │ - metrics:raw   │    │ - ELK API       │
│                 │    │ - CIDR support  │    │ - Zero dup      │    │ - Prometheus    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                                                                │
                                                                                ▼
                                                                      ┌─────────────────┐
                                                                      │ Elasticsearch   │
                                                                      │ & Prometheus    │
                                                                      └─────────────────┘
```

## Authentication

All APIs support multiple authentication methods:

### 1. API Key Authentication

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://killkrill.local/api/v1/logs
```

### 2. JWT Token Authentication

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" https://killkrill.local/api/v1/logs
```

### 3. mTLS Authentication

Configure client certificates for mutual TLS authentication.

## Logs API

### Ingest Logs (HTTP3/QUIC)

**Endpoint:** `POST /api/v1/logs`

**Headers:**

- `Content-Type: application/json`
- `X-API-Key: {api_key}` or `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "source": "my-application",
  "application": "web-server",
  "logs": [
    {
      "timestamp": "2023-12-01T10:00:00Z",
      "log_level": "info",
      "message": "User logged in successfully",
      "service_name": "auth-service",
      "hostname": "web-01",
      "logger_name": "auth.login",
      "thread_name": "main",
      "ecs_version": "8.0",
      "labels": {
        "user_id": "12345",
        "session_id": "abc123"
      },
      "tags": ["authentication", "success"],
      "trace_id": "trace-123",
      "span_id": "span-456",
      "transaction_id": "txn-789"
    }
  ]
}
```

**Response:**

```json
{
  "status": "success",
  "processed": 1,
  "timestamp": "2023-12-01T10:00:01Z"
}
```

### UDP Syslog Ingestion

KillKrill automatically assigns dedicated UDP ports for each log source:

```bash
# Example: Send syslog to assigned port
echo "<134>Dec  1 10:00:00 web-01 nginx: 192.168.1.100 - - [01/Dec/2023:10:00:00 +0000] \"GET / HTTP/1.1\" 200 1234" | nc -u killkrill.local 10001
```

Port assignments are managed through the Manager UI.

## Metrics API

### Ingest Metrics (HTTP3/QUIC)

**Endpoint:** `POST /api/v1/metrics`

**Headers:**

- `Content-Type: application/json`
- `X-API-Key: {api_key}` or `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "source": "monitoring-system",
  "metrics": [
    {
      "name": "http_requests_total",
      "type": "counter",
      "value": 1245.0,
      "labels": {
        "method": "GET",
        "status": "200",
        "endpoint": "/api/users"
      },
      "timestamp": "2023-12-01T10:00:00Z",
      "help": "Total number of HTTP requests"
    },
    {
      "name": "memory_usage_bytes",
      "type": "gauge",
      "value": 1073741824,
      "labels": {
        "instance": "web-01",
        "process": "nginx"
      },
      "timestamp": "2023-12-01T10:00:00Z",
      "help": "Current memory usage in bytes"
    }
  ]
}
```

**Response:**

```json
{
  "status": "success",
  "processed": 2,
  "timestamp": "2023-12-01T10:00:01Z"
}
```

## Manager API

### List Log Sources

**Endpoint:** `GET /api/v1/sources`

**Response:**

```json
{
  "sources": [
    {
      "id": 1,
      "name": "web-application",
      "description": "Main web application logs",
      "created_at": "2023-12-01T09:00:00Z",
      "last_seen": "2023-12-01T10:00:00Z",
      "logs_count": 12543
    }
  ],
  "total": 1
}
```

### Get Source Statistics

**Endpoint:** `GET /api/v1/sources/{source_id}/stats`

**Response:**

```json
{
  "source": {
    "id": 1,
    "name": "web-application",
    "description": "Main web application logs",
    "syslog_port": 10001,
    "enabled": true
  },
  "recent_24h": 1245,
  "status": "active"
}
```

## Health and Monitoring

### Health Check

**Endpoint:** `GET /healthz`

**Response:**

```json
{
  "status": "healthy",
  "service": "killkrill-receiver",
  "timestamp": "2023-12-01T10:00:00Z",
  "version": "1.0.0",
  "license_valid": true,
  "active_syslog_servers": 5,
  "components": {
    "redis": "ok",
    "database": "ok",
    "license": "ok",
    "xdp_filter": "ok"
  }
}
```

### Prometheus Metrics

**Endpoint:** `GET /metrics`

Returns Prometheus-formatted metrics for monitoring.

## Error Handling

All APIs return appropriate HTTP status codes:

- `200` - Success
- `400` - Bad Request (invalid JSON, missing fields)
- `401` - Unauthorized (invalid/missing API key or JWT)
- `403` - Forbidden (IP not allowed, insufficient permissions)
- `404` - Not Found (source not found)
- `429` - Too Many Requests (rate limiting)
- `500` - Internal Server Error
- `503` - Service Unavailable (health check failed)

## Rate Limiting

APIs implement rate limiting based on:

- API key/source
- IP address
- License tier

Rate limits:

- Community: 100 requests/minute
- Professional: 1000 requests/minute
- Enterprise: Unlimited

## IP/CIDR Filtering

Configure allowed IP addresses or CIDR blocks for each source:

- Single IP: `192.168.1.100`
- CIDR block: `192.168.1.0/24`
- Multiple entries: `["192.168.1.0/24", "10.0.0.100"]`

## Elastic Common Schema (ECS)

All logs are processed according to ECS 8.0 specification for consistency with Elasticsearch and Kibana.

Required fields:

- `@timestamp`
- `ecs.version`
- `message`
- `log.level`

## Examples

### Send Logs with curl

```bash
curl -X POST http://localhost:8081/api/v1/logs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "source": "test-app",
    "application": "test",
    "logs": [{
      "log_level": "info",
      "message": "Test log message",
      "service_name": "test-service"
    }]
  }'
```

### Send Metrics with curl

```bash
curl -X POST http://localhost:8082/api/v1/metrics \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "source": "test-metrics",
    "metrics": [{
      "name": "test_counter",
      "type": "counter",
      "value": 1,
      "labels": {"environment": "test"}
    }]
  }'
```

### UDP Syslog with netcat

```bash
echo "<134>$(date '+%b %d %H:%M:%S') $(hostname) test-app: Test syslog message" | nc -u localhost 10001
```
