# KillKrill Development Guide

## Resource Requirements

### Development Environment (`docker-compose.dev.yml`)

**Total RAM Usage: ~3.5GB**

| Service          | Memory Limit | CPU Limit | Purpose               |
| ---------------- | ------------ | --------- | --------------------- |
| PostgreSQL       | 256MB        | 0.5 CPU   | Database              |
| Redis            | 128MB        | 0.25 CPU  | Queuing & Cache       |
| Elasticsearch    | 1GB          | 0.5 CPU   | Log Storage           |
| Kibana           | 512MB        | 0.5 CPU   | Log Visualization     |
| Prometheus       | 256MB        | 0.25 CPU  | Metrics Storage       |
| Grafana          | 128MB        | 0.25 CPU  | Metrics Visualization |
| Manager          | 256MB        | 0.25 CPU  | Management Interface  |
| Log Receiver     | 256MB        | 0.5 CPU   | Log Ingestion         |
| Metrics Receiver | 256MB        | 0.25 CPU  | Metrics Ingestion     |
| Log Worker       | 256MB        | 0.25 CPU  | Log Processing        |
| Metrics Worker   | 256MB        | 0.25 CPU  | Metrics Processing    |

### Production Environment (`docker-compose.yml`)

**Total RAM Usage: ~16GB**

Optimized for high throughput with larger memory allocations for Elasticsearch (8GB heap) and additional performance optimizations.

## Quick Start

### 1. Start Development Environment

```bash
make dev
```

This will:

- Start all services with minimal resource allocation
- Wait for Elasticsearch to be ready
- Initialize indices and templates
- Display access URLs

### 2. Access Services

- **Manager**: http://localhost:8080 (Main management interface)
- **Kibana**: http://localhost:5601 (Log analysis)
- **Grafana**: http://localhost:3000 (Metrics dashboard, admin/admin)
- **Prometheus**: http://localhost:9090 (Raw metrics)

### 3. Test Log Ingestion

```bash
# Send test log via REST API
curl -X POST http://localhost:8081/api/v1/logs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PENG-DEMO-DEMO-DEMO-DEMO-DEMO" \
  -d '{
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "log_level": "info",
    "message": "Test log message",
    "service_name": "test-service"
  }'

# Send test log via Syslog
echo "<14>$(date) localhost test-service: Test syslog message" | nc -u localhost 514
```

### 4. Test Metrics Ingestion

```bash
curl -X POST http://localhost:8082/api/v1/metrics \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PENG-DEMO-DEMO-DEMO-DEMO-DEMO" \
  -d '{
    "name": "test_counter",
    "type": "counter",
    "value": 1,
    "labels": {"service": "test"},
    "timestamp": '$(date +%s)'
  }'
```

## Development Commands

```bash
make dev              # Start minimal dev environment (~3.5GB RAM)
make dev-full         # Start full production-spec environment (~16GB RAM)
make status           # Check service status
make logs             # View all service logs
make clean            # Stop and remove all containers
make restart          # Restart all services
```

## Service Ports

| Service          | HTTP | Additional Ports                                |
| ---------------- | ---- | ----------------------------------------------- |
| Manager          | 8080 | -                                               |
| Log Receiver     | 8081 | 8443 (HTTP3), 514/udp (Syslog), 10000-10010/udp |
| Metrics Receiver | 8082 | 8444 (HTTP3)                                    |
| Elasticsearch    | 9200 | 9300 (transport)                                |
| Kibana           | 5601 | -                                               |
| Prometheus       | 9090 | -                                               |
| Grafana          | 3000 | -                                               |
| PostgreSQL       | 5432 | -                                               |
| Redis            | 6379 | -                                               |

## Architecture Flow

```
Applications → Log/Metrics Receivers → Redis Streams → Workers → ELK/Prometheus
                                                                      ↓
                                                             Manager ← Dashboards
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f docker-compose.dev.yml logs <service-name>

# Check resource usage
docker stats

# Restart single service
docker-compose -f docker-compose.dev.yml restart <service-name>
```

### Elasticsearch Issues

```bash
# Check cluster health
curl http://localhost:9200/_cluster/health

# Reset if needed
docker-compose -f docker-compose.dev.yml down
docker volume rm killkrill_elasticsearch_data_dev
make dev
```

### Port Conflicts

```bash
# Check what's using ports
netstat -tulpn | grep -E ':(8080|8081|8082|9200|5601|9090|3000|5432|6379)'

# Stop conflicting services or modify ports in docker-compose.dev.yml
```

## Performance Optimization

The development environment is optimized for:

- **Low resource usage** for laptops/workstations
- **Fast startup times** with smaller data retention
- **Debug logging** for troubleshooting
- **Hot-reload** support for development

For performance testing, use `make dev-full` which provides production-scale resource allocation.
