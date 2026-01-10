"""
KillKrill Flask Application Factory

Enterprise-grade Flask application with Flask-Security-Too integration,
JWT authentication, RBAC, monitoring, and gRPC support.

This module provides the create_app() factory function for initializing
the Flask application with all necessary components including authentication,
database connections, metrics collection, and error handling.
"""

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional

import structlog
from decouple import config
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from flask_security import Security, SQLAlchemyUserDatastore, hash_password
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from shared.auth.middleware import (
    AuthenticationError,
    MultiAuthMiddleware,
    verify_jwt_token,
)

# Import shared modules
from shared.config.settings import KillKrillConfig, get_config
from shared.monitoring.metrics import MetricsCollector, export_metrics

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
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@dataclass
class AppConfig:
    """Configuration for Flask application"""

    env: str
    debug: bool
    testing: bool
    jwt_secret: str
    jwt_expiry_hours: int
    sqlalchemy_database_uri: str
    sqlalchemy_track_modifications: bool
    sqlalchemy_echo: bool
    max_content_length: int
    json_sort_keys: bool


class RequestIdMiddleware:
    """Middleware to add correlation IDs to all requests"""

    def __init__(self, app: Flask):
        self.app = app
        app.before_request(self.before_request)
        app.after_request(self.after_request)

    def before_request(self) -> None:
        """Generate correlation ID for request"""
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        g.correlation_id = correlation_id
        g.start_time = datetime.utcnow()

    def after_request(self, response):
        """Log request details and add correlation ID to response"""
        duration = (datetime.utcnow() - g.start_time).total_seconds()

        log_data = {
            "correlation_id": g.correlation_id,
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_seconds": duration,
            "client_ip": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", "unknown"),
        }

        if response.status_code >= 400:
            logger.warning("request_completed", **log_data)
        else:
            logger.info("request_completed", **log_data)

        response.headers["X-Correlation-ID"] = g.correlation_id
        return response


class AuthenticationMiddleware:
    """Middleware for JWT and multi-method authentication"""

    def __init__(self, app: Flask, auth_middleware: MultiAuthMiddleware):
        self.app = app
        self.auth_middleware = auth_middleware
        app.before_request(self.before_request)

    def before_request(self) -> None:
        """Authenticate request and populate g.auth_context"""
        # Skip authentication for public endpoints
        public_endpoints = [
            "/healthz",
            "/metrics",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
        ]

        if request.path in public_endpoints:
            g.auth_context = None
            return

        # Extract headers and query params
        headers = {k.lower(): v for k, v in request.headers.items()}
        query_params = dict(request.args)

        # Authenticate request
        auth_result = self.auth_middleware.authenticate_request(headers, query_params)

        if auth_result and auth_result.get("authenticated"):
            g.auth_context = auth_result
        else:
            g.auth_context = None


class MetricsMiddleware:
    """Middleware for collecting request metrics"""

    def __init__(self, app: Flask, metrics_collector: MetricsCollector):
        self.app = app
        self.metrics_collector = metrics_collector
        app.after_request(self.after_request)

    def after_request(self, response):
        """Collect metrics for request"""
        try:
            method = request.method
            endpoint = request.path
            status = str(response.status_code)
            duration = (datetime.utcnow() - g.start_time).total_seconds()

            self.metrics_collector.record_request(method, endpoint, status, duration)
        except Exception as e:
            logger.error("metrics_collection_error", error=str(e))

        return response


def create_config(env: str = None) -> AppConfig:
    """Create Flask configuration based on environment"""
    if env is None:
        env = os.getenv("FLASK_ENV", "development")

    base_config = {
        "jwt_secret": config("JWT_SECRET", default="killkrill-secret-dev-only"),
        "jwt_expiry_hours": 24,
        "sqlalchemy_track_modifications": False,
        "max_content_length": 16 * 1024 * 1024,  # 16MB
        "json_sort_keys": False,
    }

    db_uri = config(
        "DATABASE_URL",
        default="postgresql://killkrill:killkrill123@localhost:5432/killkrill",
    )

    if env == "production":
        return AppConfig(
            env="production",
            debug=False,
            testing=False,
            sqlalchemy_database_uri=db_uri,
            sqlalchemy_echo=False,
            **base_config,
        )
    elif env == "testing":
        return AppConfig(
            env="testing",
            debug=True,
            testing=True,
            sqlalchemy_database_uri="sqlite:///:memory:",
            sqlalchemy_echo=True,
            **base_config,
        )
    else:  # development
        return AppConfig(
            env="development",
            debug=True,
            testing=False,
            sqlalchemy_database_uri=db_uri,
            sqlalchemy_echo=True,
            **base_config,
        )


def setup_database(app: Flask) -> SQLAlchemy:
    """Initialize SQLAlchemy database"""
    db = SQLAlchemy(app)
    return db


def setup_security(app: Flask, db: SQLAlchemy) -> Security:
    """Setup Flask-Security-Too"""
    from models import Role, User

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security = Security(app, user_datastore, hash_password=hash_password)

    return security


def setup_jwt(app: Flask, config: AppConfig) -> JWTManager:
    """Setup Flask-JWT-Extended"""
    app.config["JWT_SECRET_KEY"] = config.jwt_secret
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=config.jwt_expiry_hours)
    app.config["JWT_ALGORITHM"] = "HS256"

    jwt = JWTManager(app)

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        # This would typically query the database for the user
        return {"user_id": identity}

    return jwt


def setup_metrics(app: Flask) -> MetricsCollector:
    """Setup Prometheus metrics collection"""
    metrics_collector = MetricsCollector("flask-backend")
    return metrics_collector


def register_blueprints(app: Flask) -> None:
    """Register API blueprints"""
    from app.api.v1 import register_blueprints as register_api_v1

    register_api_v1(app)


def register_error_handlers(app: Flask) -> None:
    """Register custom error handlers"""

    @app.errorhandler(400)
    def handle_bad_request(error):
        """Handle 400 Bad Request"""
        logger.warning(
            "bad_request_error",
            error=str(error),
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": str(error),
                    "correlation_id": g.get("correlation_id"),
                    "status_code": 400,
                }
            ),
            400,
        )

    @app.errorhandler(401)
    def handle_unauthorized(error):
        """Handle 401 Unauthorized"""
        logger.warning(
            "unauthorized_error",
            error=str(error),
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "error": "Unauthorized",
                    "message": "Authentication required",
                    "correlation_id": g.get("correlation_id"),
                    "status_code": 401,
                }
            ),
            401,
        )

    @app.errorhandler(403)
    def handle_forbidden(error):
        """Handle 403 Forbidden"""
        logger.warning(
            "forbidden_error", error=str(error), correlation_id=g.get("correlation_id")
        )
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Insufficient permissions",
                    "correlation_id": g.get("correlation_id"),
                    "status_code": 403,
                }
            ),
            403,
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 Not Found"""
        logger.warning(
            "not_found_error", path=request.path, correlation_id=g.get("correlation_id")
        )
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": f"Resource not found: {request.path}",
                    "correlation_id": g.get("correlation_id"),
                    "status_code": 404,
                }
            ),
            404,
        )

    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 Internal Server Error"""
        logger.error(
            "internal_server_error",
            error=str(error),
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "correlation_id": g.get("correlation_id"),
                    "status_code": 500,
                }
            ),
            500,
        )

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle all unhandled exceptions"""
        logger.error(
            "unhandled_exception",
            error=str(error),
            error_type=type(error).__name__,
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "correlation_id": g.get("correlation_id"),
                    "status_code": 500,
                }
            ),
            500,
        )


def register_health_endpoint(app: Flask, config: KillKrillConfig) -> None:
    """Register /healthz health check endpoint"""

    @app.route("/healthz", methods=["GET"])
    def healthz():
        """Health check endpoint"""
        return (
            jsonify(
                {
                    "status": "healthy",
                    "service": "killkrill-flask-backend",
                    "version": config.version,
                    "timestamp": datetime.utcnow().isoformat(),
                    "environment": os.getenv("FLASK_ENV", "development"),
                }
            ),
            200,
        )


def register_metrics_endpoint(app: Flask, metrics_collector: MetricsCollector) -> None:
    """Register /metrics Prometheus metrics endpoint"""

    @app.route("/metrics", methods=["GET"])
    def metrics():
        """Prometheus metrics endpoint"""
        metrics_data = export_metrics(metrics_collector.registry)
        return metrics_data, 200, {"Content-Type": "text/plain; charset=utf-8"}


def register_auth_endpoints(app: Flask, config: AppConfig) -> None:
    """Register authentication endpoints"""

    @app.route("/api/v1/auth/login", methods=["POST"])
    def login():
        """Login endpoint - returns JWT token"""
        from flask import request

        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        # TODO: Verify credentials against database
        # For now, accept any credentials
        access_token = create_access_token(
            identity=username,
            expires_delta=timedelta(hours=config.jwt_expiry_hours),
            additional_claims={
                "username": username,
                "roles": ["viewer"],
                "permissions": ["read"],
            },
        )

        logger.info(
            "user_login", username=username, correlation_id=g.get("correlation_id")
        )

        return (
            jsonify(
                {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": config.jwt_expiry_hours * 3600,
                }
            ),
            200,
        )

    @app.route("/api/v1/auth/verify", methods=["GET"])
    @jwt_required()
    def verify_token():
        """Verify JWT token"""
        identity = get_jwt_identity()
        return (
            jsonify(
                {
                    "valid": True,
                    "identity": identity,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    @app.route("/api/v1/auth/logout", methods=["POST"])
    @jwt_required()
    def logout():
        """Logout endpoint"""
        identity = get_jwt_identity()
        logger.info(
            "user_logout", identity=identity, correlation_id=g.get("correlation_id")
        )
        return jsonify({"message": "Logged out successfully"}), 200


def require_role(*roles: str):
    """Decorator to require specific roles"""

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            from flask_jwt_extended import get_jwt

            claims = get_jwt()
            user_roles = claims.get("roles", [])

            if not any(role in user_roles for role in roles):
                logger.warning(
                    "insufficient_permissions",
                    required_roles=roles,
                    user_roles=user_roles,
                    correlation_id=g.get("correlation_id"),
                )
                return (
                    jsonify(
                        {
                            "error": "Forbidden",
                            "message": "Insufficient permissions",
                            "correlation_id": g.get("correlation_id"),
                        }
                    ),
                    403,
                )

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(*permissions: str):
    """Decorator to require specific permissions"""

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            from flask_jwt_extended import get_jwt

            claims = get_jwt()
            user_permissions = claims.get("permissions", [])

            if not any(perm in user_permissions for perm in permissions):
                logger.warning(
                    "insufficient_permissions",
                    required_permissions=permissions,
                    user_permissions=user_permissions,
                    correlation_id=g.get("correlation_id"),
                )
                return (
                    jsonify(
                        {
                            "error": "Forbidden",
                            "message": "Insufficient permissions",
                            "correlation_id": g.get("correlation_id"),
                        }
                    ),
                    403,
                )

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def create_app(env: str = None) -> Flask:
    """
    Flask application factory

    Creates and configures a Flask application with all necessary components:
    - Database (SQLAlchemy with PyDAL)
    - Authentication (Flask-Security-Too, JWT, multi-method)
    - CORS support
    - Prometheus metrics
    - Error handling
    - Request logging with correlation IDs
    - gRPC support (runs on separate port)

    Args:
        env: Environment name ('development', 'testing', 'production')

    Returns:
        Configured Flask application instance
    """
    # Create Flask app
    app = Flask(__name__)

    # Load configuration
    app_config = create_config(env)
    config_dict = {
        "ENV": app_config.env,
        "DEBUG": app_config.debug,
        "TESTING": app_config.testing,
        "SQLALCHEMY_DATABASE_URI": app_config.sqlalchemy_database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": app_config.sqlalchemy_track_modifications,
        "SQLALCHEMY_ECHO": app_config.sqlalchemy_echo,
        "MAX_CONTENT_LENGTH": app_config.max_content_length,
        "JSON_SORT_KEYS": app_config.json_sort_keys,
        "JWT_SECRET_KEY": app_config.jwt_secret,
    }
    app.config.update(config_dict)

    # Setup database
    db = setup_database(app)
    app.db = db

    # Setup JWT
    jwt = setup_jwt(app, app_config)
    app.jwt = jwt

    # Setup security (Flask-Security-Too)
    try:
        security = setup_security(app, db)
        app.security = security
    except Exception as e:
        logger.warning("security_setup_warning", error=str(e))

    # Setup CORS
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": config("CORS_ORIGINS", default="*").split(","),
                "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-API-Key",
                    "X-Correlation-ID",
                ],
                "expose_headers": ["X-Correlation-ID"],
                "supports_credentials": True,
                "max_age": 3600,
            }
        },
    )

    # Get KillKrill config
    killkrill_config = get_config()

    # Setup metrics
    metrics_collector = setup_metrics(app)
    app.metrics_collector = metrics_collector

    # Setup authentication middleware
    auth_middleware = MultiAuthMiddleware(app_config.jwt_secret)

    # Register middleware
    RequestIdMiddleware(app)
    AuthenticationMiddleware(app, auth_middleware)
    MetricsMiddleware(app, metrics_collector)

    # Register endpoints
    register_health_endpoint(app, killkrill_config)
    register_metrics_endpoint(app, metrics_collector)
    register_auth_endpoints(app, app_config)

    # Register blueprints
    try:
        register_blueprints(app)
    except ImportError as e:
        logger.warning("blueprints_import_warning", error=str(e))

    # Register error handlers
    register_error_handlers(app)

    # Create database tables
    with app.app_context():
        try:
            db.create_all()
            logger.info("database_initialized", environment=app_config.env)
        except Exception as e:
            logger.error(
                "database_initialization_error",
                error=str(e),
                environment=app_config.env,
            )

    logger.info("flask_app_created", environment=app_config.env, debug=app_config.debug)

    return app


if __name__ == "__main__":
    # Development server - run with proper logging
    app = create_app(env="development")
    app.run(host="0.0.0.0", port=5000, debug=True)
