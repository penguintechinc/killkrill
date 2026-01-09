# KillKrill Deployment Guide

## Overview

KillKrill is designed for enterprise-scale deployment with high availability, scalability, and security. This guide covers deployment strategies from development to production.

## Prerequisites

### System Requirements

**Minimum Requirements:**

- 4 CPU cores
- 8 GB RAM
- 100 GB storage
- Docker 20.10+
- Docker Compose 2.0+

**Recommended Production:**

- 8+ CPU cores
- 32+ GB RAM
- 500+ GB SSD storage
- Load balancer
- Monitoring infrastructure

### Network Requirements

**Ports:**

- 8080: Manager UI
- 8081: Log Receiver (HTTP3/QUIC)
- 8082: Metrics Receiver
- 10000-11000/udp: Syslog receivers
- 5601: Kibana
- 3000: Grafana
- 9090: Prometheus

**Network Access:**

- Outbound HTTPS to `license.penguintech.io`
- Internal service communication
- Client access to receivers

## Quick Start

### 1. Environment Setup

```bash
# Clone repository
git clone https://github.com/penguintechinc/killkrill.git
cd killkrill

# Copy environment template
cp .env.example .env

# Edit configuration
vim .env
```

### 2. License Configuration

Obtain a license key from PenguinTech:

```bash
# Set license in .env
LICENSE_KEY=PENG-XXXX-XXXX-XXXX-XXXX-XXXX
PRODUCT_NAME=killkrill
```

### 3. Start Services

```bash
# Development deployment
make dev

# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. Verify Deployment

```bash
# Check health
curl http://localhost:8080/healthz
curl http://localhost:8081/healthz
curl http://localhost:8082/healthz

# Access UIs
open http://localhost:8080  # Manager (admin/admin123)
open http://localhost:3000  # Grafana (admin/killkrill123)
open http://localhost:5601  # Kibana
```

## Production Deployment

### Docker Compose Production

Create `docker-compose.prod.yml`:

```yaml
version: "3.8"

services:
  # Override for production
  manager:
    environment:
      - LOG_LEVEL=WARN
      - GIN_MODE=release
    restart: always
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  receiver:
    restart: always
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  metrics:
    restart: always
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  processor:
    restart: always
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  # External load balancer
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infrastructure/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./infrastructure/nginx/ssl:/etc/ssl/nginx
    depends_on:
      - manager
      - receiver
      - metrics
```

### Kubernetes Deployment

```bash
# Deploy to Kubernetes
kubectl apply -f infrastructure/k8s/namespace.yaml
kubectl apply -f infrastructure/k8s/configmap.yaml
kubectl apply -f infrastructure/k8s/secrets.yaml
kubectl apply -f infrastructure/k8s/services/
kubectl apply -f infrastructure/k8s/deployments/
```

### Helm Charts

```bash
# Install with Helm
helm repo add killkrill https://charts.penguintech.io
helm install killkrill killkrill/killkrill \
  --set license.key="PENG-XXXX-XXXX-XXXX-XXXX-XXXX" \
  --set ingress.enabled=true \
  --set ingress.hostname="killkrill.company.com"
```

## High Availability Setup

### Database HA

**PostgreSQL with Replication:**

```yaml
services:
  postgres-primary:
    image: postgres:15-alpine
    environment:
      - POSTGRES_REPLICATION_MODE=master
      - POSTGRES_REPLICATION_USER=replicator
      - POSTGRES_REPLICATION_PASSWORD=repl_password

  postgres-replica:
    image: postgres:15-alpine
    environment:
      - POSTGRES_REPLICATION_MODE=slave
      - POSTGRES_MASTER_HOST=postgres-primary
      - POSTGRES_REPLICATION_USER=replicator
      - POSTGRES_REPLICATION_PASSWORD=repl_password
```

### Redis HA

**Redis Sentinel:**

```yaml
services:
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes

  redis-sentinel:
    image: redis:7-alpine
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./infrastructure/redis/sentinel.conf:/etc/redis/sentinel.conf
```

### Load Balancing

**Nginx Configuration:**

```nginx
upstream killkrill_manager {
    server manager-1:8080;
    server manager-2:8080;
    server manager-3:8080;
}

upstream killkrill_receiver {
    server receiver-1:8081;
    server receiver-2:8081;
    server receiver-3:8081;
}

server {
    listen 80;
    server_name killkrill.company.com;

    location / {
        proxy_pass http://killkrill_manager;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/v1/logs {
        proxy_pass http://killkrill_receiver;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Security Configuration

### SSL/TLS Setup

```bash
# Generate certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout infrastructure/nginx/ssl/killkrill.key \
  -out infrastructure/nginx/ssl/killkrill.crt \
  -subj "/CN=killkrill.company.com"

# Update nginx config for HTTPS
```

### Firewall Rules

```bash
# Allow only required ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8080/tcp  # Manager (internal)
ufw allow 8081/tcp  # Receiver (internal)
ufw allow 10000:11000/udp  # Syslog range
ufw enable
```

### Secret Management

**Using Docker Secrets:**

```yaml
services:
  manager:
    secrets:
      - license_key
      - jwt_secret
      - db_password

secrets:
  license_key:
    file: ./secrets/license_key.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
  db_password:
    file: ./secrets/db_password.txt
```

## Monitoring and Alerting

### Prometheus Targets

```yaml
# prometheus.yml
scrape_configs:
  - job_name: "killkrill"
    static_configs:
      - targets:
          - "manager:8080"
          - "receiver:8081"
          - "metrics:8082"
          - "processor:8083"
    scrape_interval: 15s
```

### Grafana Dashboards

Import pre-built dashboards:

- KillKrill System Overview
- Log Ingestion Metrics
- Metrics Collection Stats
- Infrastructure Health

### AlertManager Rules

```yaml
# alerts/killkrill.yml
groups:
  - name: killkrill
    rules:
      - alert: KillKrillServiceDown
        expr: up{job="killkrill"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "KillKrill service is down"

      - alert: HighLogIngestionRate
        expr: rate(killkrill_logs_received_total[5m]) > 1000
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High log ingestion rate detected"
```

## Backup and Recovery

### Database Backup

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups/killkrill"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
docker exec killkrill-postgres pg_dump -U killkrill killkrill > \
  "$BACKUP_DIR/killkrill_${DATE}.sql"

# Compress and upload to S3 (optional)
gzip "$BACKUP_DIR/killkrill_${DATE}.sql"
aws s3 cp "$BACKUP_DIR/killkrill_${DATE}.sql.gz" \
  s3://your-backup-bucket/killkrill/
```

### Redis Backup

```bash
# Redis data backup
docker exec killkrill-redis redis-cli BGSAVE
docker cp killkrill-redis:/data/dump.rdb \
  /backups/killkrill/redis_${DATE}.rdb
```

### Configuration Backup

```bash
# Backup configurations
tar -czf "/backups/killkrill/config_${DATE}.tar.gz" \
  infrastructure/ \
  .env \
  docker-compose.yml
```

## Scaling

### Horizontal Scaling

**Scale Receivers:**

```bash
docker-compose up -d --scale receiver=3
```

**Scale Processors:**

```bash
docker-compose up -d --scale processor=5
```

### Vertical Scaling

**Increase Resources:**

```yaml
services:
  receiver:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: "2.0"
```

## Troubleshooting

### Common Issues

**1. License Validation Fails**

```bash
# Check license server connectivity
curl -H "Authorization: Bearer YOUR_LICENSE_KEY" \
  https://license.penguintech.io/api/v2/validate

# Verify DNS resolution
nslookup license.penguintech.io
```

**2. High Memory Usage**

```bash
# Check container memory usage
docker stats

# Restart services if needed
docker-compose restart processor
```

**3. Redis Connection Issues**

```bash
# Test Redis connectivity
docker exec killkrill-redis redis-cli ping

# Check Redis logs
docker logs killkrill-redis
```

### Log Analysis

```bash
# View service logs
docker-compose logs -f receiver
docker-compose logs -f processor
docker-compose logs -f manager

# Check health endpoints
curl http://localhost:8080/healthz | jq
curl http://localhost:8081/healthz | jq
curl http://localhost:8082/healthz | jq
```

### Performance Tuning

**Optimize Redis:**

```bash
# Increase Redis memory
echo "maxmemory 2gb" >> infrastructure/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> infrastructure/redis/redis.conf
```

**Optimize Elasticsearch:**

```bash
# Increase heap size
echo "ES_JAVA_OPTS=-Xms2g -Xmx2g" >> .env
```

## Maintenance

### Updates

```bash
# Update KillKrill
git pull origin main
docker-compose pull
docker-compose up -d

# Check for breaking changes
cat CHANGELOG.md
```

### Health Checks

```bash
# Automated health check script
#!/bin/bash
SERVICES="manager receiver metrics processor"

for service in $SERVICES; do
  if ! docker-compose ps $service | grep -q "Up"; then
    echo "ALERT: $service is down"
    # Send notification
  fi
done
```

## Support

### Getting Help

- **Documentation**: [docs/](../../docs/)
- **Issues**: https://github.com/penguintechinc/killkrill/issues
- **Enterprise Support**: support@penguintech.io
- **Community**: https://community.penguintech.io

### Enterprise Features

Contact sales@penguintech.io for:

- Priority support
- Custom integrations
- On-site training
- Professional services
