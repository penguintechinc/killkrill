[![CI](https://github.com/PenguinCloud/project-template/actions/workflows/ci.yml/badge.svg)](https://github.com/PenguinCloud/project-template/actions/workflows/ci.yml)
[![Docker Build](https://github.com/PenguinCloud/project-template/actions/workflows/docker-build.yml/badge.svg)](https://github.com/PenguinCloud/project-template/actions/workflows/docker-build.yml)
[![codecov](https://codecov.io/gh/PenguinCloud/project-template/branch/main/graph/badge.svg)](https://codecov.io/gh/PenguinCloud/project-template)
[![Go Report Card](https://goreportcard.com/badge/github.com/PenguinCloud/project-template)](https://goreportcard.com/report/github.com/PenguinCloud/project-template)
[![version](https://img.shields.io/badge/version-5.1.1-blue.svg)](https://semver.org)
[![License](https://img.shields.io/badge/License-Limited%20AGPL3-blue.svg)](LICENSE.md)

```
 _  ___ _ _ _   _  _____ _ _ _
| |/ (_) | | | |/ /_ _| | | |
| ' <| | | | | ' < | || | | |
|_|\_\_|_|_|_|_|\_\___|_|_|_|

Centralized Log & Metrics Ingestion Platform
High-Performance • Zero Duplication • Enterprise Ready
```

# KillKrill - Centralized Log & Metrics Ingestion Platform

**Enterprise-Grade Centralized Logging and Metrics Collection**

KillKrill is a comprehensive centralized platform for ingesting logs and metrics from all PenguinTech applications. It provides high-performance HTTP3/QUIC and UDP Syslog receivers with Redis Streams queuing, ensuring zero duplication while delivering to ELK stack for logs and Prometheus for metrics.
## ✨ Key Features

### 🏭 Centralized Collection
- **Single Platform**: Unified ingestion for all PenguinTech application logs and metrics
- **Zero Duplication**: Redis Streams consumer groups guarantee single processing
- **High Throughput**: Designed for enterprise-scale log and metrics volume

### 🔒 Security & Authentication
- **Multi-Protocol Security**: API key, JWT, mTLS authentication
- **IP/CIDR Filtering**: Support for single IPs and subnet notation (192.168.1.0/24)
- **TLS 1.2+ Enforcement**: Secure transport with HTTP3/QUIC support
- **XDP Packet Validation**: High-performance packet filtering at kernel level

### 🚀 Performance Optimized
- **XDP Integration**: Kernel-level packet processing for minimal latency
- **Redis Streams**: High-performance queuing with guaranteed delivery
- **HTTP3/QUIC**: Modern transport protocols for optimal performance
- **Zero-Copy Processing**: Optimized data paths for maximum throughput

### 🏢 Enterprise Integration
- **PenguinTech Licensing**: Integrated with `https://license.penguintech.io`
- **ELK Stack**: Pre-configured Elasticsearch, Logstash, and Kibana
- **Prometheus Stack**: Metrics collection with Grafana dashboards
- **Real-time Monitoring**: Comprehensive metrics and alerting

### 🔄 Reliable Processing
- **Consumer Groups**: Guaranteed single processing per destination
- **Message ACK**: Required acknowledgment prevents data loss
- **Failure Recovery**: Automatic handling of failed workers
- **Health Monitoring**: Real-time status of all components

## 🛠️ Quick Start

```bash
# Clone and setup
git clone https://github.com/penguintechinc/killkrill.git
cd killkrill
make setup                    # Install dependencies and setup environment
make dev                      # Start development environment
```

### Access Services
- **Manager UI**: http://localhost:8080 (Source management and configuration)
- **Grafana**: http://localhost:3000 (Metrics dashboards and monitoring)
- **Kibana**: http://localhost:5601 (Log search and analysis)
- **Prometheus**: http://localhost:9090 (Metrics collection)

## 🏗️ Architecture

### Data Flow
```
Logs: Applications → killkrill-receiver → Redis Streams → killkrill-processor → Elasticsearch API
Metrics: Applications → killkrill-metrics → Redis Streams → killkrill-processor → Prometheus API
```

### Core Components
- **killkrill-receiver**: Log ingestion with HTTP3/QUIC + UDP Syslog, XDP validation
- **killkrill-metrics**: Centralized metrics collection API (HTTP3/QUIC)
- **killkrill-processor**: Redis Streams consumer, outputs to Elasticsearch and Prometheus APIs
- **killkrill-manager**: py4web WebUI for management and configuration
- **Infrastructure**: ELK Stack + Prometheus + Redis Streams + PostgreSQL + ElastAlert

### Processing Guarantee
- Redis Streams consumer groups ensure zero duplication
- Message acknowledgment prevents data loss
- Failed worker recovery maintains processing continuity

## 📖 Documentation

- **Getting Started**: [docs/development/](docs/development/)
- **API Reference**: [docs/api/](docs/api/)
- **Deployment Guide**: [docs/deployment/](docs/deployment/)
- **Architecture Overview**: [docs/architecture/](docs/architecture/)
- **License Integration**: [docs/licensing/](docs/licensing/)

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Maintainers
- **Primary**: creatorsemailhere@penguintech.group
- **General**: info@penguintech.group
- **Company**: [www.penguintech.io](https://www.penguintech.io)

### Community Contributors
- *Your name could be here! Submit a PR to get started.*

## 📞 Support & Resources

- **Documentation**: [./docs/](docs/)
- **Premium Support**: https://support.penguintech.group
- **Community Issues**: [GitHub Issues](../../issues)
- **License Server Status**: https://status.penguintech.io

## 📄 License

This project is licensed under the Limited AGPL3 with preamble for fair use - see [LICENSE.md](LICENSE.md) for details.
