"""
KillKrill Log Receiver - Quart Application Factory
High-performance log ingestion service with JWT authentication
"""

import os
import sys
from datetime import datetime
from quart import Quart
from quart_cors import cors
from pydal import DAL
import redis
import structlog

# Import shared ReceiverClient
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))
from receiver_client import ReceiverClient

from config import get_config

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
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def create_app() -> Quart:
    """
    Application factory for KillKrill Log Receiver

    Returns:
        Configured Quart application
    """
    app = Quart(__name__)
    config = get_config()

    # Apply configuration to app
    app.config['DEBUG'] = config.DEBUG

    # Enable CORS
    app = cors(
        app,
        allow_origin='*',
        allow_methods=['GET', 'POST', 'OPTIONS'],
        allow_headers=['Content-Type', 'Authorization']
    )

    # Initialize components
    try:
        # Redis client
        app.redis_client = redis.from_url(config.REDIS_URL, decode_responses=True)

        # PyDAL database
        app.db = DAL(config.pydal_database_url, migrate=True, fake_migrate=False)

        # Create logs table
        app.db.define_table('logs',
            app.db.Field('timestamp', 'datetime', default=datetime.utcnow),
            app.db.Field('level', 'string'),
            app.db.Field('message', 'text'),
            app.db.Field('source', 'string'),
            migrate=True
        )
        app.db.commit()

        # ReceiverClient
        app.receiver_client = None
        if config.CLIENT_ID and config.CLIENT_SECRET:
            app.receiver_client = ReceiverClient(
                api_url=config.API_URL,
                grpc_url=config.GRPC_URL,
                client_id=config.CLIENT_ID,
                client_secret=config.CLIENT_SECRET
            )

        logger.info(
            "components_initialized",
            database=config.DATABASE_URL,
            redis=config.REDIS_URL,
            api_url=config.API_URL,
            grpc_url=config.GRPC_URL
        )

    except Exception as e:
        logger.error("initialization_error", error=str(e))
        raise

    # Register lifecycle hooks
    @app.before_serving
    async def startup():
        """Async startup tasks"""
        if app.receiver_client:
            try:
                await app.receiver_client.authenticate()
                logger.info("receiver_client_authenticated")
            except Exception as e:
                logger.error("receiver_client_authentication_failed", error=str(e))

    @app.after_serving
    async def shutdown():
        """Cleanup tasks"""
        try:
            if hasattr(app, 'db'):
                app.db.close()
            if hasattr(app, 'redis_client'):
                app.redis_client.close()
            logger.info("cleanup_completed")
        except Exception as e:
            logger.error("cleanup_error", error=str(e))

    # Register blueprints
    from routes import health_bp, metrics_bp, ingest_bp, index_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(index_bp)

    logger.info(
        "application_created",
        debug=config.DEBUG,
        version="2.0.0"
    )

    return app


if __name__ == '__main__':
    config = get_config()
    app = create_app()
    app.run(
        host='0.0.0.0',
        port=config.RECEIVER_PORT,
        debug=config.DEBUG
    )
