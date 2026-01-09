"""
KillKrill API - Quart Application Factory
Enterprise observability platform backend
"""

import asyncio
import os
from datetime import datetime
from typing import Optional

import structlog
from quart import Quart, g, jsonify, request
from quart_cors import cors

from .config import QuartConfig, get_config

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
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def create_app(config_name: str = None) -> Quart:
    """
    Application factory for KillKrill API

    Args:
        config_name: Configuration environment (development, production, testing)

    Returns:
        Configured Quart application
    """
    app = Quart(__name__)

    # Load configuration
    config_name = config_name or os.getenv("FLASK_ENV", "development")
    config = QuartConfig.get_config(config_name)

    # Apply configuration to app
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DEBUG=config.DEBUG,
        TESTING=config.TESTING,
    )

    # Store config reference
    app.killkrill_config = config

    # Enable CORS
    app = cors(
        app,
        allow_origin=(
            config.CORS_ORIGINS.split(",")
            if "," in config.CORS_ORIGINS
            else config.CORS_ORIGINS
        ),
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
    )

    # Register error handlers
    register_error_handlers(app)

    # Register middleware
    register_middleware(app)

    # Register blueprints
    register_blueprints(app)

    # Register lifecycle hooks
    register_lifecycle_hooks(app)

    # Register core endpoints
    register_core_endpoints(app)

    logger.info(
        "application_created",
        environment=config_name,
        debug=config.DEBUG,
        version="2.0.0",
    )

    return app


def register_error_handlers(app: Quart) -> None:
    """Register global error handlers"""

    @app.errorhandler(400)
    async def bad_request(error):
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": (
                        str(error.description)
                        if hasattr(error, "description")
                        else "Invalid request"
                    ),
                    "status_code": 400,
                }
            ),
            400,
        )

    @app.errorhandler(401)
    async def unauthorized(error):
        return (
            jsonify(
                {
                    "error": "Unauthorized",
                    "message": "Authentication required",
                    "status_code": 401,
                }
            ),
            401,
        )

    @app.errorhandler(403)
    async def forbidden(error):
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": (
                        str(error.description)
                        if hasattr(error, "description")
                        else "Access denied"
                    ),
                    "status_code": 403,
                }
            ),
            403,
        )

    @app.errorhandler(404)
    async def not_found(error):
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": "Resource not found",
                    "status_code": 404,
                }
            ),
            404,
        )

    @app.errorhandler(429)
    async def rate_limited(error):
        return (
            jsonify(
                {
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "status_code": 429,
                }
            ),
            429,
        )

    @app.errorhandler(500)
    async def internal_error(error):
        logger.error("internal_server_error", error=str(error))
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "status_code": 500,
                }
            ),
            500,
        )


def register_middleware(app: Quart) -> None:
    """Register request/response middleware"""

    @app.before_request
    async def before_request():
        """Pre-request processing"""
        g.request_start_time = datetime.utcnow()
        g.request_id = request.headers.get("X-Request-ID", str(id(request)))

    @app.after_request
    async def after_request(response):
        """Post-request processing"""
        # Add request ID header
        response.headers["X-Request-ID"] = g.get("request_id", "unknown")

        # Calculate request duration
        if hasattr(g, "request_start_time"):
            duration = (datetime.utcnow() - g.request_start_time).total_seconds()
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            # Log request (skip health checks to reduce noise)
            if request.path not in ["/healthz", "/metrics"]:
                logger.info(
                    "request_completed",
                    method=request.method,
                    path=request.path,
                    status=response.status_code,
                    duration=duration,
                    request_id=g.get("request_id"),
                )

        return response


def register_blueprints(app: Quart) -> None:
    """Register API blueprints"""

    # Import blueprints (will be created in subsequent files)
    from .blueprints import (
        ai_analysis_bp, auth_bp, dashboard_bp, fleet_bp, infrastructure_bp,
        licensing_bp, sensors_bp, users_bp, websocket_bp,
    )

    # Register with URL prefixes
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(sensors_bp, url_prefix="/api/v1/sensors")
    app.register_blueprint(infrastructure_bp, url_prefix="/api/v1/infrastructure")
    app.register_blueprint(fleet_bp, url_prefix="/api/v1/fleet")
    app.register_blueprint(ai_analysis_bp, url_prefix="/api/v1/ai")
    app.register_blueprint(licensing_bp, url_prefix="/api/v1/license")
    app.register_blueprint(websocket_bp, url_prefix="/ws")

    logger.info("blueprints_registered", count=9)


def register_lifecycle_hooks(app: Quart) -> None:
    """Register application lifecycle hooks"""

    @app.before_serving
    async def startup():
        """Application startup"""
        logger.info("application_starting")

        # Initialize database
        from .models.database import init_database

        await init_database(app)

        # Initialize Redis
        from .services.redis_service import init_redis

        await init_redis(app)

        # Initialize license client
        from .services.license_service import init_license

        await init_license(app)

        logger.info("application_started")

    @app.after_serving
    async def shutdown():
        """Application shutdown"""
        logger.info("application_stopping")

        # Close database connections
        from .models.database import close_database

        await close_database(app)

        # Close Redis connections
        from .services.redis_service import close_redis

        await close_redis(app)

        logger.info("application_stopped")


def register_core_endpoints(app: Quart) -> None:
    """Register core application endpoints"""

    @app.route("/healthz", methods=["GET"])
    async def health():
        """Health check endpoint"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "killkrill-api",
            "version": "2.0.0",
            "components": {},
        }

        # Check database
        try:
            from .models.database import get_db

            db = await get_db()
            if db:
                health_status["components"]["database"] = "healthy"
            else:
                health_status["components"]["database"] = "unavailable"
        except Exception as e:
            health_status["components"]["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        # Check Redis
        try:
            from .services.redis_service import get_redis

            redis = await get_redis()
            if redis:
                await redis.ping()
                health_status["components"]["redis"] = "healthy"
            else:
                health_status["components"]["redis"] = "unavailable"
        except Exception as e:
            health_status["components"]["redis"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        status_code = 200 if health_status["status"] == "healthy" else 503
        return jsonify(health_status), status_code

    @app.route("/metrics", methods=["GET"])
    async def metrics():
        """Prometheus metrics endpoint"""
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from quart import Response

        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.route("/", methods=["GET"])
    async def index():
        """API root endpoint"""
        return jsonify(
            {
                "service": "KillKrill API",
                "version": "2.0.0",
                "status": "running",
                "documentation": "/api/v1/docs",
                "health": "/healthz",
                "metrics": "/metrics",
            }
        )


# Application instance for running with hypercorn
app = create_app()


if __name__ == "__main__":
    import asyncio

    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = ["0.0.0.0:8080"]
    config.workers = 4

    asyncio.run(serve(app, config))
