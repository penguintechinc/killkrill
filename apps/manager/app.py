#!/usr/bin/env python3
"""
KillKrill Manager - Enterprise Observability Management Interface
py4web WebUI for managing log sources, metrics sources, authentication, and monitoring
Similar to AWS CloudWatch Console or Google Cloud Operations Console
"""

import os
import sys
import json
import logging
import structlog
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import redis
from py4web import action, request, response, redirect, Field, DAL, Session, Flash
from py4web.utils.cors import CORS
from py4web.utils.form import Form, FormStyleBulma
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import secrets
import hashlib
from netaddr import IPNetwork, AddrFormatError

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.licensing.client import PenguinTechLicenseClient
from shared.config.settings import get_config
from shared.auth.middleware import generate_api_key, generate_jwt_token, verify_auth

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
MANAGER_PORT = config.manager_port
SYSLOG_PORT_START = config.syslog_port_start
SYSLOG_PORT_END = config.syslog_port_end

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
license_client = PenguinTechLicenseClient(LICENSE_KEY, PRODUCT_NAME)

# Database setup
db = DAL(DATABASE_URL, migrate=True, fake_migrate=False)

# Define tables
db.define_table('users',
    Field('username', 'string', length=50, unique=True, requires=lambda v: v and len(v) >= 3),
    Field('email', 'string', length=255, unique=True),
    Field('password_hash', 'string', length=255),
    Field('role', 'string', default='viewer', requires=lambda v: v in ['admin', 'operator', 'viewer']),
    Field('enabled', 'boolean', default=True),
    Field('created_at', 'datetime', default=datetime.utcnow),
    Field('last_login', 'datetime'),
    Field('api_key', 'string', length=64, unique=True),
)

db.define_table('log_sources',
    Field('name', 'string', length=100, unique=True, requires=lambda v: v and len(v) <= 100),
    Field('description', 'text'),
    Field('application_name', 'string', length=100),
    Field('api_key', 'string', length=64, unique=True),
    Field('allowed_ips', 'text'),  # JSON array of IPs/CIDRs
    Field('syslog_port', 'integer', unique=True),
    Field('enabled', 'boolean', default=True),
    Field('log_format', 'string', default='rfc3164'),
    Field('created_at', 'datetime', default=datetime.utcnow),
    Field('created_by', 'reference users'),
    Field('last_seen', 'datetime'),
    Field('logs_count', 'bigint', default=0),
    Field('packets_dropped', 'bigint', default=0),
)

db.define_table('metric_sources',
    Field('name', 'string', length=100, unique=True, requires=lambda v: v and len(v) <= 100),
    Field('description', 'text'),
    Field('api_key', 'string', length=64, unique=True),
    Field('allowed_ips', 'text'),  # JSON array of IPs/CIDRs
    Field('enabled', 'boolean', default=True),
    Field('created_at', 'datetime', default=datetime.utcnow),
    Field('created_by', 'reference users'),
    Field('last_seen', 'datetime'),
    Field('metrics_count', 'bigint', default=0),
)

db.define_table('audit_log',
    Field('user_id', 'reference users'),
    Field('action', 'string', length=100),
    Field('resource_type', 'string', length=50),
    Field('resource_id', 'string', length=100),
    Field('details', 'text'),  # JSON
    Field('timestamp', 'datetime', default=datetime.utcnow),
    Field('ip_address', 'string', length=45),
)

# Session and Flash setup
session = Session(secret="killkrill-session-key-change-in-production")
flash = Flash()

# Prometheus metrics for manager
metrics_registry = CollectorRegistry()
ui_requests_counter = Counter(
    'killkrill_manager_requests_total',
    'Total UI requests',
    ['endpoint', 'method'],
    registry=metrics_registry
)
source_operations_counter = Counter(
    'killkrill_manager_source_operations_total',
    'Total source management operations',
    ['operation', 'type'],
    registry=metrics_registry
)

def require_auth(role: str = None):
    """Decorator to require authentication and optional role"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Check session
            user_id = session.get('user_id')
            if not user_id:
                redirect('/login')
                return

            user = db.users[user_id]
            if not user or not user.enabled:
                session.clear()
                redirect('/login')
                return

            # Check role if specified
            if role and user.role != role and user.role != 'admin':
                flash.set('Insufficient permissions', 'error')
                redirect('/dashboard')
                return

            # Add user to kwargs
            kwargs['current_user'] = user
            return func(*args, **kwargs)
        return wrapper
    return decorator

def log_audit_action(user_id: int, action: str, resource_type: str, resource_id: str, details: Dict[str, Any] = None):
    """Log audit action"""
    try:
        db.audit_log.insert(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=json.dumps(details or {}),
            ip_address=request.environ.get('REMOTE_ADDR', '127.0.0.1')
        )
        db.commit()
    except Exception as e:
        logger.error("Error logging audit action", error=str(e))

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
            'service': 'killkrill-manager',
            'timestamp': datetime.utcnow().isoformat(),
            'version': config.version,
            'license_valid': license_status.get('valid', False),
            'components': {
                'redis': 'ok',
                'database': 'ok',
                'license': 'ok' if license_status.get('valid') else 'error'
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

@action('/', method=['GET'])
@action('index', method=['GET'])
def index():
    """Root redirect to dashboard"""
    if session.get('user_id'):
        redirect('/dashboard')
    else:
        redirect('/login')

@action('login', method=['GET', 'POST'])
def login():
    """Login page"""
    ui_requests_counter.labels(endpoint='login', method=request.method).inc()

    if request.method == 'POST':
        username = request.forms.get('username', '').strip()
        password = request.forms.get('password', '')

        if username and password:
            # Find user
            user = db(db.users.username == username).select().first()
            if user and user.enabled:
                # Verify password (simplified - use proper hashing in production)
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                if user.password_hash == password_hash:
                    # Login successful
                    session['user_id'] = user.id
                    session['username'] = user.username
                    session['role'] = user.role

                    # Update last login
                    db(db.users.id == user.id).update(last_login=datetime.utcnow())
                    db.commit()

                    log_audit_action(user.id, 'login', 'user', user.id)
                    flash.set(f'Welcome back, {user.username}!', 'success')
                    redirect('/dashboard')
                else:
                    flash.set('Invalid credentials', 'error')
            else:
                flash.set('Invalid credentials', 'error')
        else:
            flash.set('Please enter username and password', 'error')

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Login</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body class="has-background-light">
        <section class="hero is-primary is-fullheight">
            <div class="hero-body">
                <div class="container">
                    <div class="columns is-centered">
                        <div class="column is-4">
                            <div class="card">
                                <div class="card-content">
                                    <div class="content has-text-centered">
                                        <h1 class="title is-3">
                                            <i class="fas fa-chart-line"></i> KillKrill
                                        </h1>
                                        <p class="subtitle">Centralized Observability Platform</p>
                                    </div>

                                    {flash.get() if flash else ''}

                                    <form method="post">
                                        <div class="field">
                                            <label class="label">Username</label>
                                            <div class="control has-icons-left">
                                                <input class="input" type="text" name="username" required>
                                                <span class="icon is-small is-left">
                                                    <i class="fas fa-user"></i>
                                                </span>
                                            </div>
                                        </div>

                                        <div class="field">
                                            <label class="label">Password</label>
                                            <div class="control has-icons-left">
                                                <input class="input" type="password" name="password" required>
                                                <span class="icon is-small is-left">
                                                    <i class="fas fa-lock"></i>
                                                </span>
                                            </div>
                                        </div>

                                        <div class="field">
                                            <div class="control">
                                                <button class="button is-primary is-fullwidth">
                                                    <span class="icon">
                                                        <i class="fas fa-sign-in-alt"></i>
                                                    </span>
                                                    <span>Login</span>
                                                </button>
                                            </div>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </body>
    </html>
    """

@action('logout', method=['GET'])
def logout():
    """Logout"""
    if session.get('user_id'):
        log_audit_action(session['user_id'], 'logout', 'user', session['user_id'])
    session.clear()
    flash.set('Logged out successfully', 'success')
    redirect('/login')

@action('dashboard', method=['GET'])
@require_auth()
def dashboard(current_user=None):
    """Main dashboard"""
    ui_requests_counter.labels(endpoint='dashboard', method='GET').inc()

    # Get statistics
    stats = {
        'log_sources': db(db.log_sources.enabled == True).count(),
        'metric_sources': db(db.metric_sources.enabled == True).count(),
        'total_logs': db().select(db.log_sources.logs_count.sum()).first()[db.log_sources.logs_count.sum()] or 0,
        'total_metrics': db().select(db.metric_sources.metrics_count.sum()).first()[db.metric_sources.metrics_count.sum()] or 0,
    }

    # Get recent activity
    recent_log_sources = db(db.log_sources.enabled == True).select(
        orderby=~db.log_sources.last_seen,
        limitby=(0, 5)
    )

    recent_metric_sources = db(db.metric_sources.enabled == True).select(
        orderby=~db.metric_sources.last_seen,
        limitby=(0, 5)
    )

    # Get license info
    license_status = license_client.validate()

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Dashboard</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        {get_navbar(current_user)}

        <section class="section">
            <div class="container">
                <h1 class="title">
                    <i class="fas fa-tachometer-alt"></i> Dashboard
                </h1>

                {flash.get() if flash else ''}

                <!-- License Status -->
                <div class="notification {'is-success' if license_status.get('valid') else 'is-warning'}">
                    <strong>License Status:</strong>
                    {license_status.get('tier', 'Unknown').title()}
                    ({'Valid' if license_status.get('valid') else 'Invalid'})
                    {f"- {license_status.get('customer', '')}" if license_status.get('customer') else ''}
                </div>

                <!-- Statistics Cards -->
                <div class="columns">
                    <div class="column">
                        <div class="card">
                            <div class="card-content">
                                <div class="level">
                                    <div class="level-left">
                                        <div class="level-item">
                                            <div>
                                                <p class="title">{stats['log_sources']}</p>
                                                <p class="subtitle">Log Sources</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="level-right">
                                        <div class="level-item">
                                            <span class="icon is-large has-text-primary">
                                                <i class="fas fa-file-alt fa-2x"></i>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="column">
                        <div class="card">
                            <div class="card-content">
                                <div class="level">
                                    <div class="level-left">
                                        <div class="level-item">
                                            <div>
                                                <p class="title">{stats['metric_sources']}</p>
                                                <p class="subtitle">Metric Sources</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="level-right">
                                        <div class="level-item">
                                            <span class="icon is-large has-text-info">
                                                <i class="fas fa-chart-line fa-2x"></i>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="column">
                        <div class="card">
                            <div class="card-content">
                                <div class="level">
                                    <div class="level-left">
                                        <div class="level-item">
                                            <div>
                                                <p class="title">{stats['total_logs']:,}</p>
                                                <p class="subtitle">Total Logs</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="level-right">
                                        <div class="level-item">
                                            <span class="icon is-large has-text-success">
                                                <i class="fas fa-database fa-2x"></i>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="column">
                        <div class="card">
                            <div class="card-content">
                                <div class="level">
                                    <div class="level-left">
                                        <div class="level-item">
                                            <div>
                                                <p class="title">{stats['total_metrics']:,}</p>
                                                <p class="subtitle">Total Metrics</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="level-right">
                                        <div class="level-item">
                                            <span class="icon is-large has-text-warning">
                                                <i class="fas fa-chart-bar fa-2x"></i>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Recent Activity -->
                <div class="columns">
                    <div class="column">
                        <div class="card">
                            <header class="card-header">
                                <p class="card-header-title">
                                    <i class="fas fa-file-alt"></i>&nbsp; Recent Log Sources
                                </p>
                                <a href="/log-sources" class="card-header-icon">
                                    <span class="icon">
                                        <i class="fas fa-arrow-right"></i>
                                    </span>
                                </a>
                            </header>
                            <div class="card-content">
                                <div class="content">
                                    {get_source_list(recent_log_sources, 'log')}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="column">
                        <div class="card">
                            <header class="card-header">
                                <p class="card-header-title">
                                    <i class="fas fa-chart-line"></i>&nbsp; Recent Metric Sources
                                </p>
                                <a href="/metric-sources" class="card-header-icon">
                                    <span class="icon">
                                        <i class="fas fa-arrow-right"></i>
                                    </span>
                                </a>
                            </header>
                            <div class="card-content">
                                <div class="content">
                                    {get_source_list(recent_metric_sources, 'metric')}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Quick Actions -->
                <div class="card">
                    <header class="card-header">
                        <p class="card-header-title">
                            <i class="fas fa-plus"></i>&nbsp; Quick Actions
                        </p>
                    </header>
                    <div class="card-content">
                        <div class="buttons">
                            <a href="/log-sources/new" class="button is-primary">
                                <span class="icon">
                                    <i class="fas fa-plus"></i>
                                </span>
                                <span>Add Log Source</span>
                            </a>
                            <a href="/metric-sources/new" class="button is-info">
                                <span class="icon">
                                    <i class="fas fa-plus"></i>
                                </span>
                                <span>Add Metric Source</span>
                            </a>
                            <a href="/monitoring" class="button is-success">
                                <span class="icon">
                                    <i class="fas fa-chart-area"></i>
                                </span>
                                <span>View Monitoring</span>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </body>
    </html>
    """

def get_navbar(current_user):
    """Generate navigation bar"""
    return f"""
    <nav class="navbar is-primary" role="navigation">
        <div class="navbar-brand">
            <a class="navbar-item" href="/dashboard">
                <i class="fas fa-chart-line"></i>
                <strong>&nbsp;KillKrill</strong>
            </a>
        </div>

        <div class="navbar-menu">
            <div class="navbar-start">
                <a class="navbar-item" href="/dashboard">
                    <i class="fas fa-tachometer-alt"></i>&nbsp; Dashboard
                </a>
                <a class="navbar-item" href="/log-sources">
                    <i class="fas fa-file-alt"></i>&nbsp; Log Sources
                </a>
                <a class="navbar-item" href="/metric-sources">
                    <i class="fas fa-chart-line"></i>&nbsp; Metric Sources
                </a>
                <a class="navbar-item" href="/monitoring">
                    <i class="fas fa-chart-area"></i>&nbsp; Monitoring
                </a>
                {'<a class="navbar-item" href="/admin"><i class="fas fa-cog"></i>&nbsp; Admin</a>' if current_user.role == 'admin' else ''}
            </div>

            <div class="navbar-end">
                <div class="navbar-item has-dropdown is-hoverable">
                    <a class="navbar-link">
                        <i class="fas fa-user"></i>&nbsp; {current_user.username} ({current_user.role})
                    </a>
                    <div class="navbar-dropdown">
                        <a class="navbar-item" href="/profile">
                            <i class="fas fa-user-edit"></i>&nbsp; Profile
                        </a>
                        <hr class="navbar-divider">
                        <a class="navbar-item" href="/logout">
                            <i class="fas fa-sign-out-alt"></i>&nbsp; Logout
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </nav>
    """

def get_source_list(sources, source_type):
    """Generate source list HTML"""
    if not sources:
        return "<p class='has-text-grey'>No sources found</p>"

    html = "<div class='content'>"
    for source in sources:
        status_class = "has-text-success" if source.last_seen and (datetime.utcnow() - source.last_seen).seconds < 300 else "has-text-grey"
        count_field = 'logs_count' if source_type == 'log' else 'metrics_count'

        html += f"""
        <div class="level is-mobile">
            <div class="level-left">
                <div class="level-item">
                    <div>
                        <p class="title is-6">{source.name}</p>
                        <p class="subtitle is-7 {status_class}">
                            {getattr(source, count_field, 0):,} {source_type}s
                        </p>
                    </div>
                </div>
            </div>
            <div class="level-right">
                <div class="level-item">
                    <span class="icon {status_class}">
                        <i class="fas fa-circle"></i>
                    </span>
                </div>
            </div>
        </div>
        """

    html += "</div>"
    return html

def get_next_available_port():
    """Get next available syslog port"""
    used_ports = {row.syslog_port for row in db(db.log_sources.syslog_port != None).select(db.log_sources.syslog_port)}

    for port in range(SYSLOG_PORT_START, SYSLOG_PORT_END + 1):
        if port not in used_ports:
            return port

    return None

# Initialize admin user if none exists
def initialize_admin_user():
    """Create default admin user if none exists"""
    try:
        if db(db.users.role == 'admin').count() == 0:
            admin_password = "admin123"  # Change this in production
            password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            api_key = generate_api_key()

            db.users.insert(
                username='admin',
                email='admin@killkrill.local',
                password_hash=password_hash,
                role='admin',
                api_key=api_key
            )
            db.commit()

            logger.info("Created default admin user", username='admin', password=admin_password)
    except Exception as e:
        logger.error("Error creating admin user", error=str(e))

if __name__ == '__main__':
    # Validate license on startup
    license_status = license_client.validate()
    if not license_status.get('valid'):
        logger.error("Invalid license", status=license_status)
        sys.exit(1)

    # Initialize admin user
    initialize_admin_user()

    logger.info("Starting KillKrill Manager",
                port=MANAGER_PORT,
                license_tier=license_status.get('tier'))

    # Start server
    from py4web import main
    main.start(
        host='0.0.0.0',
        port=MANAGER_PORT,
        apps_folder=os.path.dirname(__file__)
    )