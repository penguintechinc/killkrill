"""
WSGI/ASGI entry point for KillKrill API
Used by Hypercorn to run the application
"""

import os
import sys

# Add the app directory to Python path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from middleware.auth import AuthMiddleware
from models.database import close_database, get_db, init_database
from quart import Quart, g, jsonify, request
from quart_cors import cors
from services.license_service import (check_feature, get_license_info,
                                      init_license)
from services.redis_service import close_redis, get_redis, init_redis

# Import with absolute imports
from config import QuartConfig, get_config

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
    """Application factory for KillKrill API"""
    app = Quart(__name__)

    # Load configuration
    config_name = config_name or os.getenv("FLASK_ENV", "development")
    config = QuartConfig.get_config(config_name)

    # Apply configuration
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DEBUG=config.DEBUG,
        TESTING=config.TESTING,
    )
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
    @app.before_request
    async def before_request():
        g.request_start_time = datetime.utcnow()
        g.request_id = request.headers.get("X-Request-ID", str(id(request)))
        await AuthMiddleware.authenticate()

    @app.after_request
    async def after_request(response):
        response.headers["X-Request-ID"] = g.get("request_id", "unknown")
        if hasattr(g, "request_start_time"):
            duration = (datetime.utcnow() - g.request_start_time).total_seconds()
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return response

    # Register blueprints
    register_blueprints(app)

    # Lifecycle hooks
    @app.before_serving
    async def startup():
        logger.info("application_starting")
        await init_database(app)
        await init_redis(app)
        await init_license(app)
        logger.info("application_started")

    @app.after_serving
    async def shutdown():
        logger.info("application_stopping")
        await close_database(app)
        await close_redis(app)
        logger.info("application_stopped")

    # Core endpoints
    @app.route("/healthz", methods=["GET"])
    async def health():
        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "killkrill-api",
                "version": "2.0.0",
            }
        )

    @app.route("/metrics", methods=["GET"])
    async def metrics():
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from quart import Response

        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.route("/", methods=["GET"])
    async def index():
        return jsonify(
            {"service": "KillKrill API", "version": "2.0.0", "status": "running"}
        )

    logger.info("application_created", environment=config_name)
    return app


def register_error_handlers(app: Quart) -> None:
    @app.errorhandler(400)
    async def bad_request(error):
        return jsonify({"error": "Bad Request", "status_code": 400}), 400

    @app.errorhandler(401)
    async def unauthorized(error):
        return jsonify({"error": "Unauthorized", "status_code": 401}), 401

    @app.errorhandler(403)
    async def forbidden(error):
        return jsonify({"error": "Forbidden", "status_code": 403}), 403

    @app.errorhandler(404)
    async def not_found(error):
        return jsonify({"error": "Not Found", "status_code": 404}), 404

    @app.errorhandler(500)
    async def internal_error(error):
        return jsonify({"error": "Internal Server Error", "status_code": 500}), 500


def register_blueprints(app: Quart) -> None:
    from blueprints.ai_analysis import ai_analysis_bp
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.fleet import fleet_bp
    from blueprints.infrastructure import infrastructure_bp
    from blueprints.licensing import licensing_bp
    from blueprints.sensors import sensors_bp
    from blueprints.users import users_bp
    from blueprints.websocket import websocket_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(sensors_bp, url_prefix="/api/v1/sensors")
    app.register_blueprint(infrastructure_bp, url_prefix="/api/v1/infrastructure")
    app.register_blueprint(fleet_bp, url_prefix="/api/v1/fleet")
    app.register_blueprint(ai_analysis_bp, url_prefix="/api/v1/ai")
    app.register_blueprint(licensing_bp, url_prefix="/api/v1/license")
    app.register_blueprint(websocket_bp, url_prefix="/ws")


# Create app instance
app = create_app()


if __name__ == "__main__":
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = ["0.0.0.0:8080"]
    asyncio.run(serve(app, config))
