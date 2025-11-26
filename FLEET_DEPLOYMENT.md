# Fleet Integration Deployment Guide

This guide covers the complete deployment of Fleet Open Source integrated with KillKrill for comprehensive infrastructure monitoring and device management.

## 🚀 Quick Start

```bash
# 1. Clone and configure
git clone <repository-url>
cd killkrill
cp .env.example .env

# 2. Configure Fleet and AI settings in .env
nano .env

# 3. Start all services including Fleet
docker-compose up -d

# 4. Access the integrated management portal
open http://localhost:8080
```

## 📋 Prerequisites

- Docker & Docker Compose
- 16GB+ RAM (recommended for full stack)
- 50GB+ disk space
- Network access for AI endpoints (if using Enterprise features)

## 🏗️ Architecture Overview

### Integrated Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   KillKrill     │    │     Fleet       │    │   AI Analysis   │
│   Platform      │    │   Management    │    │  (Enterprise)   │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • Log Receiver  │◄──►│ • Fleet Server  │◄──►│ • Metric AI     │
│ • Metrics API   │    │ • MySQL DB      │    │ • Anomaly Det   │
│ • ELK Stack     │    │ • Redis Cache   │    │ • Alerts        │
│ • Prometheus    │    │ • Agent Mgmt    │    │ • Reports       │
│ • Manager UI    │    │ • Query Engine  │    │ • OpenAI API    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

```
Fleet Agents → Fleet Server → Log Receiver → ELK Stack
     ↓              ↓              ↓            ↓
   Metrics → Prometheus ← Manager UI ← AI Analysis
```

## ⚙️ Configuration

### 1. Fleet Configuration

Edit `.env` file:

```bash
# Fleet Database (MySQL)
FLEET_MYSQL_DATABASE=fleet
FLEET_MYSQL_USER=fleet
FLEET_MYSQL_PASSWORD=fleet123
FLEET_MYSQL_ROOT_PASSWORD=fleetroot123
FLEET_MYSQL_PORT=3307

# Fleet Server
FLEET_PORT=8084
FLEET_SERVER_URL=https://killkrill-fleet.local:8084
FLEET_JWT_KEY=supersecretfleetjwtkey123456

# Fleet Agent Enrollment
FLEET_ENROLL_SECRET=changeme-fleet-secret-123
```

### 2. AI Analysis Configuration (Enterprise)

```bash
# OpenAI-Compatible Endpoint
AI_ENDPOINT_URL=https://api.anthropic.com/v1/messages
AI_API_KEY=your-api-key-here
AI_MODEL=claude-3-haiku-20240307
AI_PROVIDER=anthropic

# Alternative providers:
# AI_PROVIDER=openai
# AI_ENDPOINT_URL=https://api.openai.com/v1/chat/completions
# AI_MODEL=gpt-4o-mini

# AI_PROVIDER=ollama
# AI_ENDPOINT_URL=http://localhost:11434/api/generate
# AI_MODEL=llama2
```

## 🚀 Deployment Steps

### Step 1: Infrastructure Deployment

```bash
# Start core KillKrill services
docker-compose up -d postgres redis elasticsearch logstash kibana prometheus grafana

# Wait for services to be ready
./scripts/wait-for-services.sh

# Start Fleet infrastructure
docker-compose up -d fleet-mysql fleet-redis fleet-server

# Start KillKrill services with Fleet integration
docker-compose up -d log-receiver metrics-receiver manager
```

### Step 2: Fleet Agent Deployment

#### Option A: Ansible Deployment (Recommended)

```bash
# Configure inventory
nano infrastructure/ansible/inventory/hypervisors.yml

# Update with your hosts:
hypervisors:
  hosts:
    hypervisor-01:
      ansible_host: 192.168.1.10
      ansible_user: root
      host_type: hypervisor
    k8s-node-01:
      ansible_host: 192.168.1.20
      ansible_user: ubuntu
      host_type: kubernetes_node

# Deploy agents
cd infrastructure/ansible
ansible-playbook -i inventory/hypervisors.yml playbooks/deploy-fleet-agents.yml
```

#### Option B: Kubernetes DaemonSet

```bash
# Deploy Fleet agents to Kubernetes cluster
kubectl apply -k k8s/fleet-agents/base/

# Check deployment status
kubectl get daemonset -n fleet-agents
kubectl get pods -n fleet-agents
```

#### Option C: Manual Installation

```bash
# Download and install Fleet agent
curl -L https://github.com/fleetdm/fleet/releases/latest/download/fleetd-linux-amd64.deb -o fleetd.deb
sudo dpkg -i fleetd.deb

# Configure agent
sudo mkdir -p /opt/orbit
sudo tee /opt/orbit/orbit.yml << EOF
fleet_url: https://killkrill-fleet.local:8084
enroll_secret: changeme-fleet-secret-123
host_identifier: hostname
log_level: info
tls_skip_verify: true
EOF

# Start agent
sudo systemctl enable --now orbit
```

## 🎯 Access & Management

### Management Portal

Primary access point: http://localhost:8080

Available services:
- **Fleet Management**: Device monitoring and queries
- **Grafana Dashboards**: Metrics visualization
- **Kibana Logs**: Log search and analysis
- **AI Analysis**: Intelligent insights (Enterprise)
- **Prometheus**: Raw metrics access
- **AlertManager**: Alert management

### Service Endpoints

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Manager Portal | 8080 | http://localhost:8080 | Unified management interface |
| Fleet Server | 8084 | http://localhost:8084 | Fleet web interface |
| Grafana | 3000 | http://localhost:3000 | Direct Grafana access |
| Kibana | 5601 | http://localhost:5601 | Direct Kibana access |
| Prometheus | 9090 | http://localhost:9090 | Direct Prometheus access |

## 📊 Monitoring & Dashboards

### Pre-built Dashboards

**Fleet Overview Dashboard** (`fleet-overview`)
- Host status and connectivity
- Agent enrollment statistics
- Query performance metrics
- Log ingestion rates

**Fleet Security Dashboard** (`fleet-security`)
- Security event monitoring
- Vulnerability assessments
- Compliance tracking
- Threat detection

### Custom Queries

Access Fleet query interface through:
- Manager Portal: http://localhost:8080 → Fleet Management
- Direct Fleet UI: http://localhost:8084

Example queries:
```sql
-- System information
SELECT hostname, platform, osquery_version FROM system_info;

-- Running processes
SELECT name, pid, path FROM processes WHERE name LIKE '%docker%';

-- Network connections
SELECT pid, family, protocol, local_address, remote_address FROM process_open_sockets WHERE remote_port != 0;
```

## 🤖 AI Analysis (Enterprise)

### Enabling AI Analysis

1. **Configure AI Provider** in `.env`:
```bash
AI_ENDPOINT_URL=https://api.anthropic.com/v1/messages
AI_API_KEY=your-api-key-here
AI_PROVIDER=anthropic
```

2. **Set Enterprise License**:
```bash
LICENSE_KEY=PENG-XXXX-XXXX-XXXX-XXXX-ENTERPRISE
```

3. **Access AI Features**:
- Automated analysis runs every 4 hours
- Manual analysis: http://localhost:8080 → AI Analysis
- View insights and recommendations

### Supported AI Providers

| Provider | Endpoint URL | Model Examples |
|----------|--------------|----------------|
| Anthropic Claude | `https://api.anthropic.com/v1/messages` | `claude-3-haiku-20240307` |
| OpenAI | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` |
| Azure OpenAI | `https://your-resource.openai.azure.com/...` | `gpt-4` |
| Ollama (Local) | `http://localhost:11434/api/generate` | `llama2`, `codellama` |

## 🔧 Troubleshooting

### Common Issues

**Fleet Server Won't Start**
```bash
# Check MySQL connectivity
docker-compose logs fleet-mysql

# Check Fleet server logs
docker-compose logs fleet-server

# Verify database initialization
docker-compose exec fleet-mysql mysql -u fleet -pfleet123 -e "SHOW DATABASES;"
```

**Agents Not Enrolling**
```bash
# Check agent logs
sudo journalctl -u orbit -f

# Verify network connectivity
curl -k https://killkrill-fleet.local:8084/healthz

# Check enrollment secret
grep -i enroll /opt/orbit/orbit.yml
```

**Missing Metrics**
```bash
# Check Prometheus targets
open http://localhost:9090/targets

# Verify log forwarding
docker-compose logs log-receiver | grep fleet

# Check Redis streams
docker-compose exec redis redis-cli XINFO STREAM fleet-logs
```

### Health Checks

```bash
# Overall system health
curl http://localhost:8080/services/health

# Fleet server health
curl http://localhost:8084/healthz

# Service connectivity
docker-compose ps
```

## 🔒 Security Considerations

### Production Deployment

1. **Change Default Passwords**:
```bash
# Generate secure passwords
FLEET_MYSQL_PASSWORD=$(openssl rand -base64 32)
FLEET_JWT_KEY=$(openssl rand -base64 64)
FLEET_ENROLL_SECRET=$(openssl rand -base64 32)
```

2. **Enable TLS**:
- Replace development certificates in `infrastructure/fleet/certs/`
- Update `TLS_CERT_PATH` and `TLS_KEY_PATH` in `.env`
- Set `FLEET_TLS_SKIP_VERIFY=false`

3. **Network Security**:
- Restrict Fleet server access (port 8084)
- Use VPN/private networks for agent communication
- Enable firewall rules for required ports only

4. **API Security**:
- Generate and rotate API tokens regularly
- Implement IP allowlisting for sensitive endpoints
- Enable audit logging for all administrative actions

## 📈 Scaling Considerations

### Horizontal Scaling

```bash
# Scale Fleet server
docker-compose up -d --scale fleet-server=3

# Scale KillKrill workers
docker-compose up -d --scale log-worker=3 --scale metrics-worker=3
```

### Performance Tuning

**MySQL Optimization** (production):
```sql
-- Add to Fleet MySQL configuration
innodb_buffer_pool_size = 8G
innodb_log_file_size = 2G
max_connections = 500
```

**Redis Optimization**:
```bash
# Add to fleet-redis configuration
maxmemory 2gb
maxmemory-policy allkeys-lru
```

## 📚 Additional Resources

- **Fleet Documentation**: https://fleetdm.com/docs
- **KillKrill Architecture**: [docs/architecture/](docs/architecture/)
- **API Documentation**: [docs/api/](docs/api/)
- **Runbooks**: [docs/runbooks/](docs/runbooks/)

## 🆘 Support

- **Community Issues**: [GitHub Issues](../../issues)
- **Enterprise Support**: support@penguintech.group
- **Documentation**: [./docs/](docs/)

---

**Deployment Version**: 1.0.0
**Last Updated**: 2025-01-15
**Compatibility**: KillKrill 5.1.1 + Fleet 4.57.0