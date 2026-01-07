"""
WSGI application entry point for KillKrill Flask Backend

This module provides the WSGI application instance for production servers like Gunicorn.
Used when running: gunicorn wsgi:app

Environment Variables:
    FLASK_ENV: development|testing|production (default: production)
    DATABASE_URL: PostgreSQL/MySQL connection string
    JWT_SECRET: JWT signing secret
    LOG_LEVEL: DEBUG|INFO|WARNING|ERROR|CRITICAL (default: INFO)
"""

import os
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Determine environment
FLASK_ENV = os.getenv("FLASK_ENV", "production")

try:
    # Import and create Flask app
    from app import create_app

    # Create application instance
    app = create_app(env=FLASK_ENV)

    logger.info(f"WSGI application initialized (env={FLASK_ENV})")

except Exception as e:
    logger.error(f"Failed to initialize WSGI application: {str(e)}")
    sys.exit(1)


if __name__ == "__main__":
    # This should not be called directly; use Gunicorn instead
    logger.warning("wsgi.py should not be run directly. Use: gunicorn wsgi:app")
    app.run(host="0.0.0.0", port=5000, debug=False)
