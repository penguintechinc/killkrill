#!/usr/bin/env python3
"""
KillKrill Log Receiver - JWT Auth with ReceiverClient
Unified HTTP/gRPC server with JWT authentication and automatic protocol fallback
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import redis
import structlog
from prometheus_client import Counter, generate_latest
from py4web import DAL, action, request, response

# Import shared ReceiverClient
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))
from receiver_client import (AuthenticationError, ConnectionError,
                             ReceiverClient)

logger = structlog.get_logger(__name__)

# Configuration
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://killkrill:killkrill123@postgres:5432/killkrill"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
RECEIVER_PORT = int(os.environ.get("RECEIVER_PORT", "8081"))
API_URL = os.environ.get("API_URL", "http://flask-backend:5000")
GRPC_URL = os.environ.get("GRPC_URL", "flask-backend:50051")
CLIENT_ID = os.environ.get("RECEIVER_CLIENT_ID", "log-receiver")
CLIENT_SECRET = os.environ.get("RECEIVER_CLIENT_SECRET", "")

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace("postgresql://", "postgres://")

# Initialize components
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

    # Create basic tables
    db.define_table(
        "logs",
        db.Field("timestamp", "datetime", default=datetime.utcnow),
        db.Field("level", "string"),
        db.Field("message", "text"),
        db.Field("source", "string"),
        migrate=True,
    )

    db.commit()
    print(f"✓ KillKrill Log Receiver initialized")
    print(f"✓ Database: {DATABASE_URL}")
    print(f"✓ Redis: {REDIS_URL}")

except Exception as e:
    print(f"✗ Initialization error: {e}")
    sys.exit(1)

# Initialize ReceiverClient with JWT auth and gRPC/REST fallback
receiver_client = None
if CLIENT_ID and CLIENT_SECRET:
    try:
        receiver_client = ReceiverClient(
            api_url=API_URL,
            grpc_url=GRPC_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )
        print(f"✓ ReceiverClient initialized")
        print(f"✓ API URL: {API_URL}")
        print(f"✓ gRPC URL: {GRPC_URL}")
    except Exception as e:
        print(f"⚠ ReceiverClient initialization error: {e}")


# Authenticate receiver client on startup
async def startup_authentication():
    global receiver_client
    if receiver_client:
        try:
            await receiver_client.authenticate()
            logger.info("receiver_client_authenticated")
        except Exception as e:
            logger.error("receiver_client_authentication_failed", error=str(e))


# Run async startup
try:
    asyncio.run(startup_authentication())
except Exception as e:
    logger.warning("async_startup_failed", error=str(e))

# Metrics
logs_received = Counter(
    "killkrill_logs_received_total", "Total logs received", ["level"]
)
health_checks = Counter(
    "killkrill_log_receiver_health_checks_total", "Health checks", ["status"]
)


@action("healthz", method=["GET"])
async def health_check():
    """Health check endpoint"""
    try:
        components = {}

        # Test Redis
        try:
            redis_client.ping()
            components["redis"] = "ok"
        except Exception as e:
            components["redis"] = f"error: {str(e)}"

        # Test database
        try:
            db.executesql("SELECT 1")
            components["database"] = "ok"
        except Exception as e:
            components["database"] = f"error: {str(e)}"

        # Check receiver client
        if receiver_client:
            try:
                is_healthy = await receiver_client.health_check()
                components["receiver_client"] = "ok" if is_healthy else "degraded"
            except Exception as e:
                components["receiver_client"] = f"error: {str(e)}"

        # Overall status
        status = (
            "healthy" if all(v == "ok" for v in components.values()) else "degraded"
        )
        if any("error" in str(v) for v in components.values()):
            status = "unhealthy"

        health_checks.labels(status="ok" if status == "healthy" else "error").inc()

        response.headers["Content-Type"] = "application/json"
        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "killkrill-log-receiver",
            "components": components,
        }
    except Exception as e:
        health_checks.labels(status="error").inc()
        response.status = 503
        response.headers["Content-Type"] = "application/json"
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@action("metrics", method=["GET"])
def metrics():
    """Prometheus metrics endpoint"""
    response.headers["Content-Type"] = "text/plain; version=0.0.4; charset=utf-8"
    return generate_latest()


@action("api/v1/logs", method=["POST"])
async def ingest_logs():
    """Log ingestion endpoint with ReceiverClient submission"""
    try:
        log_data = request.json

        # Basic validation
        if not log_data:
            response.status = 400
            return {"error": "No JSON data provided"}

        # Extract log fields
        timestamp = log_data.get("timestamp")
        if timestamp:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp = datetime.utcnow()

        level = log_data.get("log_level", log_data.get("level", "info"))
        message = log_data.get("message", str(log_data))
        source = log_data.get("service_name", log_data.get("source", "unknown"))

        # Store in database
        log_id = db.logs.insert(
            timestamp=timestamp, level=level, message=message, source=source
        )
        db.commit()

        # Send to Redis stream
        stream_data = {
            "id": str(log_id),
            "timestamp": timestamp.isoformat(),
            "level": level,
            "message": message,
            "source": source,
        }
        redis_client.xadd("logs", stream_data)

        # Submit to backend via ReceiverClient (gRPC with REST fallback)
        if receiver_client:
            try:
                log_payload = {
                    "timestamp": timestamp.isoformat(),
                    "level": level,
                    "message": message,
                    "source": source,
                }
                await receiver_client.submit_logs([log_payload])
                logger.info("log_submitted", log_id=log_id)
            except (AuthenticationError, ConnectionError) as e:
                # Log submission error but continue (non-fatal)
                logger.warning("receiver_submission_error", error=str(e))

        # Update metrics
        logs_received.labels(level=level).inc()

        response.headers["Content-Type"] = "application/json"
        return {
            "status": "accepted",
            "log_id": log_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("log_ingestion_error", error=str(e))
        response.status = 500
        response.headers["Content-Type"] = "application/json"
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}


@action("index", method=["GET"])
def index():
    """Basic status page"""
    log_count = db(db.logs).count()
    return f"""
    <html>
    <head><title>KillKrill Log Receiver</title></head>
    <body>
        <h1>KillKrill Log Receiver</h1>
        <p>High-performance log ingestion service</p>
        <ul>
            <li><a href="/healthz">Health Check</a></li>
            <li><a href="/metrics">Metrics</a></li>
            <li><strong>Total logs received:</strong> {log_count}</li>
        </ul>
        <h2>Usage</h2>
        <p>Send logs via POST to <code>/api/v1/logs</code></p>
        <pre>
curl -X POST http://localhost:8081/api/v1/logs \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer PENG-DEMO-DEMO-DEMO-DEMO-DEMO" \\
  -d '{{"log_level": "info", "message": "Test log", "service_name": "test"}}'
        </pre>
    </body>
    </html>
    """


if __name__ == "__main__":
    print(f"Starting KillKrill Log Receiver on port {RECEIVER_PORT}")

    # Import py4web server
    from py4web.core import wsgi
    from rocket3 import Rocket

    app = wsgi()
    server = Rocket(("0.0.0.0", RECEIVER_PORT), "wsgi", {"wsgi_app": app})

    try:
        print(f"✓ Log Receiver listening on http://0.0.0.0:{RECEIVER_PORT}")
        print(f"✓ Send logs to http://localhost:{RECEIVER_PORT}/api/v1/logs")
        server.start()
    except KeyboardInterrupt:
        print("Log Receiver shutdown requested")
        server.stop()
