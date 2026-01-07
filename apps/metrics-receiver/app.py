"""KillKrill Metrics Receiver - Quart application."""
import asyncio
from datetime import datetime
from quart import Quart
from quart_cors import cors
from pydal import DAL, Field
import redis.asyncio as aioredis
from prometheus_client import Counter
import structlog

from shared.receiver_client import ReceiverClient
from config import Config

logger = structlog.get_logger(__name__)


def create_app(config: Config = None) -> Quart:
    """Application factory for metrics-receiver."""
    app = Quart(__name__)
    app = cors(app, allow_origin="*")

    # Load configuration
    if config is None:
        config = Config()

    # Convert PostgreSQL URL to PyDAL format
    pydal_database_url = config.pydal_database_url

    # Initialize database
    app.db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

    # Create tables
    try:
        app.db.define_table('received_metrics',
            Field('metric_name', 'string', length=255),
            Field('metric_type', 'string', length=50),
            Field('metric_value', 'double'),
            Field('labels', 'text'),  # JSON
            Field('timestamp', 'datetime', default=datetime.utcnow),
            Field('source_ip', 'string', length=45),
            migrate=True
        )
        app.db.commit()
    except Exception as table_error:
        logger.warning("table_creation_skipped", error=str(table_error))

    # Initialize Redis client (async)
    app.redis_client = None

    # Initialize ReceiverClient
    app.receiver_client = None
    if config.RECEIVER_CLIENT_ID and config.RECEIVER_CLIENT_SECRET:
        app.receiver_client = ReceiverClient(
            api_url=config.API_URL,
            grpc_url=config.GRPC_URL,
            client_id=config.RECEIVER_CLIENT_ID,
            client_secret=config.RECEIVER_CLIENT_SECRET
        )

    # Prometheus metrics
    app.received_metrics_counter = Counter(
        'killkrill_metrics_received_total',
        'Total metrics received',
        ['metric_type']
    )

    # Store config
    app.config.from_object(config)

    # Register blueprints
    from routes import health, metrics, ingest
    app.register_blueprint(health.bp)
    app.register_blueprint(metrics.bp)
    app.register_blueprint(ingest.bp)

    @app.before_serving
    async def startup():
        """Initialize async components."""
        # Initialize Redis
        app.redis_client = await aioredis.from_url(
            config.REDIS_URL,
            decode_responses=True
        )

        # Authenticate receiver client
        if app.receiver_client:
            try:
                await app.receiver_client.authenticate()
                logger.info("receiver_client_authenticated")
            except Exception as e:
                logger.error("receiver_client_authentication_failed", error=str(e))

        logger.info("killkrill_metrics_receiver_initialized")

    @app.after_serving
    async def shutdown():
        """Cleanup async components."""
        if app.redis_client:
            await app.redis_client.close()

        logger.info("killkrill_metrics_receiver_shutdown")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8082)
