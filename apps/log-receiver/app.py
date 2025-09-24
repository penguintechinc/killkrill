#!/usr/bin/env python3
"""
KillKrill Log Receiver
High-performance log ingestion with HTTP3/QUIC API and UDP Syslog
Features:
- HTTP3/QUIC API endpoints
- UDP Syslog receivers with dedicated ports per source
- XDP packet validation for CIDR/IP filtering
- Elastic Common Schema compliance
- Redis Streams for zero-duplication processing
"""

import os
import sys
import json
import asyncio
import logging
import structlog
import socket
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import redis
import httpx
from py4web import action, request, response, Field, DAL
from py4web.utils.cors import CORS
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import pydantic
from netaddr import IPNetwork, AddrFormatError
import uuid
import hashlib

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.licensing.client import PenguinTechLicenseClient
from shared.config.settings import get_config
from shared.auth.middleware import verify_auth
from xdp_manager import XDPFilterManager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configuration
config = get_config()
REDIS_URL = config.redis_url
DATABASE_URL = config.database_url
LICENSE_KEY = config.license_key
PRODUCT_NAME = config.product_name
RECEIVER_PORT = config.receiver_port
SYSLOG_PORT_START = config.syslog_port_start
SYSLOG_PORT_END = config.syslog_port_end

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
license_client = PenguinTechLicenseClient(LICENSE_KEY, PRODUCT_NAME)

# Database setup
db = DAL(DATABASE_URL, migrate=True, fake_migrate=False)

# Define tables for log sources
db.define_table('log_sources',
    Field('name', 'string', requires=lambda v: v and len(v) <= 100, unique=True),
    Field('description', 'text'),
    Field('application_name', 'string', length=100),
    Field('api_key', 'string', length=64, unique=True),
    Field('allowed_ips', 'text'),  # JSON array of IPs/CIDRs
    Field('syslog_port', 'integer', unique=True),
    Field('enabled', 'boolean', default=True),
    Field('log_format', 'string', default='rfc3164'),  # rfc3164, rfc5424, json
    Field('created_at', 'datetime', default=datetime.utcnow),
    Field('last_seen', 'datetime'),
    Field('logs_count', 'bigint', default=0),
    Field('packets_dropped', 'bigint', default=0),
)

db.define_table('received_logs',
    Field('source_id', 'reference log_sources'),
    Field('timestamp', 'datetime', default=datetime.utcnow),
    Field('severity', 'string', length=20),
    Field('facility', 'string', length=50),
    Field('hostname', 'string', length=255),
    Field('program', 'string', length=100),
    Field('message', 'text'),
    Field('source_ip', 'string', length=45),
    Field('raw_log', 'text'),
    Field('ecs_version', 'string', default='8.0'),  # Elastic Common Schema version
)

# Prometheus metrics
metrics_registry = CollectorRegistry()
logs_received_counter = Counter(
    'killkrill_logs_received_total',
    'Total logs received',
    ['source', 'protocol', 'severity'],
    registry=metrics_registry
)
packets_dropped_counter = Counter(
    'killkrill_packets_dropped_total',
    'Total packets dropped',
    ['source', 'reason'],
    registry=metrics_registry
)
processing_time = Histogram(
    'killkrill_log_processing_seconds',
    'Time spent processing logs',
    ['source', 'protocol'],
    registry=metrics_registry
)
active_syslog_servers = Gauge(
    'killkrill_active_syslog_servers',
    'Number of active syslog servers',
    registry=metrics_registry
)

# Global state for UDP servers and XDP filter
syslog_servers: Dict[int, 'SyslogServer'] = {}
xdp_filter_manager: Optional[XDPFilterManager] = None
xdp_filter_active = False


class LogEntry(pydantic.BaseModel):
    """Elastic Common Schema compliant log entry"""
    timestamp: datetime = pydantic.Field(default_factory=datetime.utcnow)
    log_level: str = pydantic.Field(..., regex=r'^(trace|debug|info|warn|error|fatal)$')
    message: str = pydantic.Field(..., max_length=10000)
    service_name: str = pydantic.Field(..., max_length=100)
    hostname: Optional[str] = pydantic.Field(None, max_length=255)
    logger_name: Optional[str] = pydantic.Field(None, max_length=100)
    thread_name: Optional[str] = pydantic.Field(None, max_length=50)

    # ECS fields
    ecs_version: str = "8.0"
    labels: Optional[Dict[str, str]] = {}
    tags: Optional[List[str]] = []

    # Application context
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    transaction_id: Optional[str] = None

    # Error details (if applicable)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_stack_trace: Optional[str] = None


class LogBatch(pydantic.BaseModel):
    """Batch of log entries"""
    source: str = pydantic.Field(..., max_length=100)
    application: str = pydantic.Field(..., max_length=100)
    logs: List[LogEntry] = pydantic.Field(..., min_items=1, max_items=1000)


class SyslogServer:
    """UDP Syslog server with XDP filtering"""

    def __init__(self, port: int, source_id: int, allowed_ips: List[str]):
        self.port = port
        self.source_id = source_id
        self.allowed_ips = allowed_ips
        self.socket = None
        self.running = False
        self.thread = None

    def start(self):
        """Start the syslog server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.port))
            self.running = True

            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()

            logger.info("Syslog server started", port=self.port, source_id=self.source_id)

        except Exception as e:
            logger.error("Failed to start syslog server", port=self.port, error=str(e))
            raise

    def stop(self):
        """Stop the syslog server"""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join(timeout=5)

        logger.info("Syslog server stopped", port=self.port)

    def _run_server(self):
        """Main server loop"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65536)
                client_ip = addr[0]

                # XDP-style IP filtering
                if not self._validate_source_ip(client_ip):
                    packets_dropped_counter.labels(
                        source=f"source_{self.source_id}",
                        reason="ip_not_allowed"
                    ).inc()
                    continue

                # Process the syslog message
                self._process_syslog_message(data.decode('utf-8', errors='ignore'), client_ip)

            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    logger.error("Error in syslog server", port=self.port, error=str(e))

    def _validate_source_ip(self, client_ip: str) -> bool:
        """Validate source IP against allowed networks (XDP-style filtering)"""
        if not self.allowed_ips:
            return True

        try:
            for network_str in self.allowed_ips:
                try:
                    network = IPNetwork(network_str)
                    if client_ip in network:
                        return True
                except (AddrFormatError, ValueError):
                    continue
            return False
        except Exception:
            return False

    def _process_syslog_message(self, message: str, client_ip: str):
        """Process incoming syslog message"""
        try:
            with processing_time.labels(
                source=f"source_{self.source_id}",
                protocol="syslog"
            ).time():

                # Parse syslog message (simplified RFC3164 parsing)
                parsed = self._parse_syslog_rfc3164(message)

                # Store in database
                db.received_logs.insert(
                    source_id=self.source_id,
                    timestamp=parsed.get('timestamp', datetime.utcnow()),
                    severity=parsed.get('severity', 'info'),
                    facility=parsed.get('facility', 'user'),
                    hostname=parsed.get('hostname', ''),
                    program=parsed.get('program', ''),
                    message=parsed.get('message', message),
                    source_ip=client_ip,
                    raw_log=message
                )

                # Send to Redis Streams
                stream_data = {
                    'source_id': self.source_id,
                    'protocol': 'syslog',
                    'timestamp': parsed.get('timestamp', datetime.utcnow()).isoformat(),
                    'severity': parsed.get('severity', 'info'),
                    'facility': parsed.get('facility', 'user'),
                    'hostname': parsed.get('hostname', ''),
                    'program': parsed.get('program', ''),
                    'message': parsed.get('message', message),
                    'source_ip': client_ip,
                    'raw_log': message,
                    'ecs_version': '8.0'
                }

                redis_client.xadd('logs:raw', stream_data)

                # Update metrics
                logs_received_counter.labels(
                    source=f"source_{self.source_id}",
                    protocol="syslog",
                    severity=parsed.get('severity', 'info')
                ).inc()

                # Update source stats
                db(db.log_sources.id == self.source_id).update(
                    last_seen=datetime.utcnow(),
                    logs_count=db.log_sources.logs_count + 1
                )
                db.commit()

        except Exception as e:
            logger.error("Error processing syslog message",
                        source_id=self.source_id, error=str(e))

    def _parse_syslog_rfc3164(self, message: str) -> Dict[str, Any]:
        """Simple RFC3164 syslog parser"""
        result = {
            'timestamp': datetime.utcnow(),
            'severity': 'info',
            'facility': 'user',
            'hostname': '',
            'program': '',
            'message': message
        }

        try:
            # Extract priority
            if message.startswith('<') and '>' in message:
                end_pos = message.find('>')
                priority_str = message[1:end_pos]
                priority = int(priority_str)

                # Calculate facility and severity
                facility_num = priority >> 3
                severity_num = priority & 7

                facilities = ['kernel', 'user', 'mail', 'daemon', 'auth', 'syslog',
                             'lpr', 'news', 'uucp', 'cron', 'authpriv', 'ftp']
                severities = ['emergency', 'alert', 'critical', 'error',
                             'warning', 'notice', 'info', 'debug']

                result['facility'] = facilities[facility_num] if facility_num < len(facilities) else 'user'
                result['severity'] = severities[severity_num] if severity_num < len(severities) else 'info'

                # Rest of message
                remaining = message[end_pos + 1:].strip()

                # Parse timestamp, hostname, program
                parts = remaining.split(' ', 3)
                if len(parts) >= 3:
                    result['hostname'] = parts[1] if len(parts) > 1 else ''
                    result['program'] = parts[2].split(':')[0] if len(parts) > 2 else ''
                    result['message'] = parts[3] if len(parts) > 3 else remaining
                else:
                    result['message'] = remaining

        except (ValueError, IndexError):
            # If parsing fails, use entire message
            result['message'] = message

        return result


def verify_source_access(source_id: int, client_ip: str, api_key: str = None) -> bool:
    """Verify access to log source"""
    try:
        source = db.log_sources[source_id]
        if not source or not source.enabled:
            return False

        # Check API key if provided
        if api_key and source.api_key != api_key:
            return False

        # Check IP access
        if source.allowed_ips:
            allowed_networks = json.loads(source.allowed_ips)
            for network_str in allowed_networks:
                try:
                    network = IPNetwork(network_str)
                    if client_ip in network:
                        return True
                except Exception:
                    continue
            return False

        return True

    except Exception as e:
        logger.error("Error verifying source access", source_id=source_id, error=str(e))
        return False


@action('healthz', method=['GET'])
@CORS()
def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_client.ping()

        # Check database connection
        db.executesql("SELECT 1")

        # Check license
        license_status = license_client.validate()

        return {
            'status': 'healthy',
            'service': 'killkrill-receiver',
            'timestamp': datetime.utcnow().isoformat(),
            'version': config.version,
            'license_valid': license_status.get('valid', False),
            'active_syslog_servers': len(syslog_servers),
            'components': {
                'redis': 'ok',
                'database': 'ok',
                'license': 'ok' if license_status.get('valid') else 'error',
                'xdp_filter': 'ok' if xdp_filter_active else 'inactive'
            }
        }
    except Exception as e:
        response.status = 503
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@action('metrics', method=['GET'])
def prometheus_metrics():
    """Prometheus metrics endpoint"""
    response.headers['Content-Type'] = 'text/plain'
    return generate_latest(metrics_registry)


@action('api/v1/xdp/stats', method=['GET'])
@CORS()
def xdp_statistics():
    """XDP filtering statistics endpoint"""
    try:
        if xdp_filter_manager:
            stats = xdp_filter_manager.get_statistics()
        else:
            stats = {"enabled": False, "message": "XDP not available"}

        return stats
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get XDP statistics: {str(e)}'}


@action('api/v1/xdp/status', method=['GET'])
@CORS()
def xdp_status():
    """XDP filter status endpoint"""
    try:
        if xdp_filter_manager:
            status = xdp_filter_manager.get_status()
        else:
            status = {"available": False, "loaded": False, "message": "XDP not initialized"}

        return status
    except Exception as e:
        response.status = 500
        return {'error': f'Failed to get XDP status: {str(e)}'}


@action('api/v1/logs', method=['POST'])
@CORS()
def receive_logs_http():
    """Receive logs via HTTP3/QUIC API"""
    try:
        # Get client IP
        client_ip = request.environ.get('REMOTE_ADDR', '127.0.0.1')

        # Authenticate request
        headers = {k.lower(): v for k, v in request.headers.items()}
        query_params = dict(request.query)

        authenticated, auth_context = verify_auth(
            headers, query_params, config.jwt_secret, client_ip=client_ip
        )

        if not authenticated:
            response.status = 401
            return {'error': 'Authentication required'}

        # Parse and validate request
        try:
            data = request.json
            batch = LogBatch.parse_obj(data)
        except Exception as e:
            response.status = 400
            return {'error': f'Invalid request format: {str(e)}'}

        # Find or create source
        source = db(db.log_sources.name == batch.source).select().first()
        if not source:
            response.status = 404
            return {'error': 'Source not found'}

        # Verify access
        if not verify_source_access(source.id, client_ip):
            response.status = 403
            return {'error': 'Access denied'}

        # Process logs
        with processing_time.labels(
            source=batch.source,
            protocol="http"
        ).time():
            processed_count = process_log_batch(source.id, batch, client_ip)

        return {
            'status': 'success',
            'processed': processed_count,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("Error processing HTTP logs", error=str(e))
        response.status = 500
        return {'error': 'Internal server error'}


def process_log_batch(source_id: int, batch: LogBatch, client_ip: str) -> int:
    """Process a batch of log entries"""
    processed = 0

    for log_entry in batch.logs:
        try:
            # Store in database
            db.received_logs.insert(
                source_id=source_id,
                timestamp=log_entry.timestamp,
                severity=log_entry.log_level,
                facility='application',
                hostname=log_entry.hostname or '',
                program=log_entry.logger_name or batch.application,
                message=log_entry.message,
                source_ip=client_ip,
                raw_log=log_entry.json(),
                ecs_version=log_entry.ecs_version
            )

            # Send to Redis Streams with ECS compliance
            stream_data = {
                'source_id': source_id,
                'protocol': 'http',
                'timestamp': log_entry.timestamp.isoformat(),
                'log_level': log_entry.log_level,
                'message': log_entry.message,
                'service_name': log_entry.service_name,
                'hostname': log_entry.hostname or '',
                'logger_name': log_entry.logger_name or '',
                'thread_name': log_entry.thread_name or '',
                'ecs_version': log_entry.ecs_version,
                'labels': json.dumps(log_entry.labels or {}),
                'tags': json.dumps(log_entry.tags or []),
                'trace_id': log_entry.trace_id or '',
                'span_id': log_entry.span_id or '',
                'transaction_id': log_entry.transaction_id or '',
                'error_type': log_entry.error_type or '',
                'error_message': log_entry.error_message or '',
                'error_stack_trace': log_entry.error_stack_trace or '',
                'source_ip': client_ip,
                'application': batch.application
            }

            redis_client.xadd('logs:raw', stream_data)

            # Update metrics
            logs_received_counter.labels(
                source=batch.source,
                protocol="http",
                severity=log_entry.log_level
            ).inc()

            processed += 1

        except Exception as e:
            logger.error("Error processing log entry", error=str(e))
            continue

    # Update source stats
    if processed > 0:
        db(db.log_sources.id == source_id).update(
            last_seen=datetime.utcnow(),
            logs_count=db.log_sources.logs_count + processed
        )
        db.commit()

    return processed


def start_syslog_server(source_id: int, port: int, allowed_ips: List[str]):
    """Start a syslog server for a specific source"""
    try:
        if port in syslog_servers:
            logger.warning("Syslog server already running", port=port)
            return

        server = SyslogServer(port, source_id, allowed_ips)
        server.start()
        syslog_servers[port] = server

        # Update metrics
        active_syslog_servers.set(len(syslog_servers))

    except Exception as e:
        logger.error("Failed to start syslog server", port=port, error=str(e))


def stop_syslog_server(port: int):
    """Stop a syslog server"""
    if port in syslog_servers:
        syslog_servers[port].stop()
        del syslog_servers[port]
        active_syslog_servers.set(len(syslog_servers))


def initialize_syslog_servers():
    """Initialize syslog servers for all active sources"""
    try:
        sources = db(
            (db.log_sources.enabled == True) &
            (db.log_sources.syslog_port != None)
        ).select()

        for source in sources:
            allowed_ips = json.loads(source.allowed_ips) if source.allowed_ips else []
            start_syslog_server(source.id, source.syslog_port, allowed_ips)

        logger.info("Initialized syslog servers", count=len(syslog_servers))

    except Exception as e:
        logger.error("Error initializing syslog servers", error=str(e))


if __name__ == '__main__':
    # Validate license on startup
    license_status = license_client.validate()
    if not license_status.get('valid'):
        logger.error("Invalid license", status=license_status)
        sys.exit(1)

    logger.info("Starting KillKrill Log Receiver",
                port=RECEIVER_PORT,
                syslog_port_range=f"{SYSLOG_PORT_START}-{SYSLOG_PORT_END}",
                license_tier=license_status.get('tier'))

    # Initialize XDP filter
    try:
        global xdp_filter_manager, xdp_filter_active
        xdp_filter_manager = XDPFilterManager()

        if xdp_filter_manager.is_available():
            if xdp_filter_manager.load_program():
                # Load initial CIDR rules from database
                sources = db((db.log_sources.enabled == True) &
                           (db.log_sources.allowed_ips != None)).select()

                cidr_rules = []
                allowed_ports = [RECEIVER_PORT]  # HTTP API port

                for source in sources:
                    if source.allowed_ips:
                        try:
                            ips = json.loads(source.allowed_ips)
                            for ip_cidr in ips:
                                cidr_rules.append({
                                    "cidr": ip_cidr,
                                    "port": source.syslog_port or 0,
                                    "enabled": True
                                })
                            if source.syslog_port:
                                allowed_ports.append(source.syslog_port)
                        except Exception as e:
                            logger.warning("Invalid allowed_ips for source",
                                          source_id=source.id, error=str(e))

                # Add syslog port range
                allowed_ports.extend(range(SYSLOG_PORT_START, SYSLOG_PORT_END + 1))

                xdp_filter_manager.update_cidr_rules(cidr_rules)
                xdp_filter_manager.update_allowed_ports(allowed_ports)
                xdp_filter_active = True

                logger.info("XDP filtering enabled",
                          cidr_rules=len(cidr_rules),
                          allowed_ports=len(allowed_ports))
            else:
                logger.warning("Failed to load XDP program, continuing without XDP filtering")
        else:
            logger.info("XDP not available, using application-level filtering")
    except Exception as e:
        logger.error("Error initializing XDP filter", error=str(e))
        logger.info("Continuing without XDP filtering")

    # Initialize syslog servers
    initialize_syslog_servers()

    # Start HTTP server
    from py4web import main
    main.start(
        host='0.0.0.0',
        port=RECEIVER_PORT,
        apps_folder=os.path.dirname(__file__)
    )