"""
KillKrill Manager - Quart Application
Enterprise observability management interface
"""

import os
from datetime import datetime

import redis.asyncio as redis
from pydal import DAL, Field
from quart import Quart
from quart_cors import cors
from routes import (dashboard_bp, embeds_bp, health_bp, infrastructure_bp,
                    services_bp)

from config import config


def create_app():
    """Application factory"""
    app = Quart(__name__)
    app = cors(app, allow_origin="*")

    # Load configuration
    app.config["DATABASE_URL"] = config.DATABASE_URL
    app.config["REDIS_URL"] = config.REDIS_URL
    app.config["LICENSE_KEY"] = config.LICENSE_KEY
    app.config["LOG_LEVEL"] = config.LOG_LEVEL

    # Initialize PyDAL database connection
    db = DAL(config.pydal_database_url, migrate=True, fake_migrate=False)

    # Create basic tables if they don't exist
    try:
        db.define_table(
            "health_checks",
            Field("timestamp", "datetime", default=datetime.utcnow),
            Field("status", "string", default="ok"),
            Field("component", "string"),
            migrate=True,
        )
        db.commit()
    except Exception as table_error:
        print(f"Note: Table creation skipped - {table_error}")

    # Initialize Redis client (async)
    redis_client = redis.from_url(config.REDIS_URL, decode_responses=True)

    # Store in app config
    app.config["db"] = db
    app.config["redis_client"] = redis_client

    print("✓ KillKrill Manager (Quart) initialized")

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(infrastructure_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(embeds_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=config.HOST, port=config.PORT, debug=False)
