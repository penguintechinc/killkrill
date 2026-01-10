# KillKrill Kubernetes Agent

The KillKrill Kubernetes Agent is a DaemonSet that runs on every node in your Kubernetes cluster to collect logs and metrics and send them to KillKrill receivers via HTTP3/QUIC protocol.

## Features

- **Kubernetes-native**: Designed specifically for Kubernetes environments
- **Adaptive Protocol Support**: HTTP3/QUIC primary with HTTP1.1 py4web fallback
- **Zero Duplication**: Ensures no duplicate log entries
- **Comprehensive Collection**: Logs, metrics, and Kubernetes metadata
- **Privileged Access**: Collects node-level metrics and container logs
- **Auto-discovery**: Automatically discovers pods, services, and nodes
- **Efficient Batching**: Configurable batching and compression
- **Enterprise Security**: TLS encryption and authentication
- **Intelligent Fallback**: Automatic protocol switching with recovery attempts

## Quick Start

### 1. Install the DaemonSet

```bash
# Apply the DaemonSet and related resources
kubectl apply -f killkrill-agent.yaml
```

### 2. Configure KillKrill Receivers

Update the ConfigMap with your KillKrill receiver endpoints:

```bash
kubectl patch configmap killkrill-agent-config -n killkrill-system --type merge -p '{
  "data": {
    "log-receiver-url": "https://your-killkrill-log-receiver:8443",
    "metrics-receiver-url": "https://your-killkrill-metrics-receiver:8444",
    "cluster-name": "your-cluster-name"
  }
}'
```

### 3. Set License Key

```bash
# Base64 encode your license key
echo -n "PENG-XXXX-XXXX-XXXX-XXXX-XXXX" | base64

# Update the secret
kubectl patch secret killkrill-license -n killkrill-system --type merge -p '{
  "data": {
    "license-key": "UEVORy1YWFhYLVhYWFgtWFhYWC1YWFhYLVhYWFg="
  }
}'
```

### 4. Verify Installation

```bash
# Check DaemonSet status
kubectl get daemonset killkrill-agent -n killkrill-system

# Check pod logs
kubectl logs -l app=killkrill-agent -n killkrill-system -f

# Check metrics endpoint
kubectl port-forward -n killkrill-system svc/killkrill-agent-metrics 8080:8080
curl http://localhost:8080/metrics
```

## Architecture

The KillKrill Agent consists of several components:

```
┌─────────────────────────────────────────────────────────────┐
│                    KillKrill Agent Pod                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Log Collector │  │Metrics Collector│  │Health Server│ │
│  │                 │  │                 │  │             │ │
│  │ • File watching │  │ • Kubelet API   │  │ • /healthz  │ │
│  │ • Log parsing   │  │ • cAdvisor      │  │ • /ready    │ │
│  │ • K8s metadata  │  │ • Node metrics  │  │ • /metrics  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│           │                      │                 │       │
│           v                      v                 │       │
│  ┌─────────────────┐  ┌─────────────────┐         │       │
│  │   HTTP3 Sender  │  │   HTTP3 Sender  │         │       │
│  │     (Logs)      │  │   (Metrics)     │         │       │
│  │                 │  │                 │         │       │
│  │ • QUIC protocol │  │ • QUIC protocol │         │       │
│  │ • Batching      │  │ • Batching      │         │       │
│  │ • Compression   │  │ • Compression   │         │       │
│  │ • Retries       │  │ • Retries       │         │       │
│  └─────────────────┘  └─────────────────┘         │       │
└─────────────────────────────────────────────────────────────┘
           │                      │                 │
           v                      v                 │
┌─────────────────┐  ┌─────────────────┐           │
│ KillKrill Log   │  │KillKrill Metrics│           │
│   Receiver      │  │   Receiver      │           │
└─────────────────┘  └─────────────────┘           │
                                                   │
                                                   v
                                        ┌─────────────────┐
                                        │   Prometheus    │
                                        │   Monitoring    │
                                        └─────────────────┘
```

## Configuration

### Environment Variables

The agent supports configuration via environment variables:

| Variable                         | Description                 | Default           |
| -------------------------------- | --------------------------- | ----------------- |
| `NODE_NAME`                      | Kubernetes node name        | From fieldRef     |
| `NODE_IP`                        | Node IP address             | From fieldRef     |
| `CLUSTER_NAME`                   | Cluster identifier          | `default-cluster` |
| `KILLKRILL_LOG_RECEIVER_URL`     | Log receiver endpoint       | Required          |
| `KILLKRILL_METRICS_RECEIVER_URL` | Metrics receiver endpoint   | Required          |
| `KILLKRILL_LICENSE_KEY`          | PenguinTech license key     | Required          |
| `LOG_LEVEL`                      | Logging level               | `info`            |
| `METRICS_INTERVAL`               | Metrics collection interval | `30s`             |

### ConfigMap Configuration

The agent loads configuration from `/etc/killkrill/config.yaml`:

```yaml
# Agent identification
agent:
  node_name: "${NODE_NAME}"
  cluster_name: "${CLUSTER_NAME}"

# Log collection settings
logs:
  enabled: true
  paths:
    - /var/log/pods/*/*/*.log
    - /var/log/containers/*.log

  # Kubernetes metadata enrichment
  kubernetes:
    enabled: true
    pod_metadata:
      - namespace
      - pod_name
      - container_name
      - labels
      - annotations

  # Output to KillKrill
  output:
    type: http3
    url: "${KILLKRILL_LOG_RECEIVER_URL}"
    batch_size: 1000
    flush_interval: "5s"
    compression: gzip

# Metrics collection settings
metrics:
  enabled: true
  interval: "30s"

  sources:
    - name: kubelet_node
      url: "https://localhost:10250/metrics"
    - name: cadvisor
      url: "https://localhost:10250/metrics/cadvisor"

  output:
    type: http3
    url: "${KILLKRILL_METRICS_RECEIVER_URL}"
    batch_size: 500
    flush_interval: "30s"
```

## Collected Data

### Logs

The agent collects logs from:

- **Container logs**: All container stdout/stderr logs
- **Pod logs**: Kubernetes pod logs with metadata
- **System logs**: Node-level system logs (optional)

Each log entry is enriched with:

- Kubernetes metadata (namespace, pod, container, labels, annotations)
- Node information
- Timestamp normalization
- Log level extraction
- Container runtime information

### Metrics

The agent collects metrics from:

- **Kubelet**: Node and pod resource usage
- **cAdvisor**: Container metrics
- **Node exporter**: System metrics (if available)
- **Kubernetes API**: Cluster object metrics

Metrics include:

- CPU and memory usage
- Network I/O
- Disk I/O
- Pod and container states
- Kubernetes object counts
- Custom application metrics

## Security

### Permissions

The DaemonSet requires extensive permissions to collect comprehensive data:

```yaml
# Cluster-wide read access
- apiGroups: [""]
  resources: ["nodes", "pods", "services", "endpoints", "events"]
  verbs: ["get", "list", "watch"]

# Metrics access
- apiGroups: ["metrics.k8s.io"]
  resources: ["nodes", "pods"]
  verbs: ["get", "list"]

# Node stats access
- apiGroups: [""]
  resources: ["nodes/stats"]
  verbs: ["get"]
```

### Privileged Access

The agent runs as privileged to access:

- Host filesystem for log files
- Host network for node metrics
- Host PID namespace for process information
- Kernel capabilities for system monitoring

### TLS Security

All communications use TLS encryption:

- **HTTP3/QUIC**: Encrypted transport to receivers
- **Kubelet API**: mTLS authentication
- **Certificate validation**: Configurable for development

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**

   ```bash
   # Check RBAC permissions
   kubectl auth can-i get pods --as=system:serviceaccount:killkrill-system:killkrill-agent

   # Check security context
   kubectl describe pod -l app=killkrill-agent -n killkrill-system
   ```

2. **Connection Failures**

   ```bash
   # Test receiver connectivity
   kubectl exec -it -n killkrill-system deployment/killkrill-agent -- \
     curl -k https://killkrill-log-receiver:8443/healthz

   # Check DNS resolution
   kubectl exec -it -n killkrill-system deployment/killkrill-agent -- \
     nslookup killkrill-log-receiver.killkrill-system.svc.cluster.local
   ```

3. **Log Collection Issues**

   ```bash
   # Check log directory permissions
   kubectl exec -it -n killkrill-system deployment/killkrill-agent -- \
     ls -la /var/log/pods

   # Verify container runtime detection
   kubectl logs -l app=killkrill-agent -n killkrill-system | grep "runtime"
   ```

### Debug Mode

Enable debug logging:

```bash
kubectl patch configmap killkrill-agent-config -n killkrill-system --type merge -p '{
  "data": {
    "log-level": "debug"
  }
}'

# Restart pods to pick up new config
kubectl rollout restart daemonset killkrill-agent -n killkrill-system
```

### Health Checks

Check agent health:

```bash
# Health endpoint
kubectl port-forward -n killkrill-system svc/killkrill-agent-metrics 8080:8080
curl http://localhost:8080/healthz

# Readiness check
curl http://localhost:8080/ready

# Prometheus metrics
curl http://localhost:8080/metrics | grep killkrill_agent
```

## Performance Tuning

### Resource Limits

Adjust resource requests and limits based on cluster size:

```yaml
resources:
  requests:
    memory: "128Mi" # Small clusters
    cpu: "100m"
  limits:
    memory: "512Mi" # Large clusters: 1Gi+
    cpu: "500m" # Large clusters: 1000m+
```

### Batch Configuration

Optimize batching for your network:

```yaml
# High-throughput clusters
logs:
  output:
    batch_size: 2000
    flush_interval: "10s"

metrics:
  output:
    batch_size: 1000
    flush_interval: "60s"
```

### Buffer Sizes

Adjust buffer sizes for high-volume environments:

```yaml
performance:
  worker_threads: 8
  buffer_size: "32MB"
  queue_size: 20000
  connection_pool_size: 20
```

## Monitoring

Monitor agent performance with Prometheus metrics:

```promql
# Messages sent per second
rate(killkrill_agent_sent_messages_total[5m])

# Send latency
histogram_quantile(0.95, rate(killkrill_agent_send_duration_seconds_bucket[5m]))

# Buffer utilization
killkrill_agent_buffer_size / killkrill_agent_buffer_capacity

# Error rate
rate(killkrill_agent_sent_messages_total{status!="success"}[5m])
```

## License

This software requires a valid PenguinTech license key. Contact sales@penguintech.io for licensing information.

## Support

- **Documentation**: https://docs.killkrill.io
- **Issues**: https://github.com/penguintechinc/killkrill/issues
- **Enterprise Support**: support@penguintech.io
