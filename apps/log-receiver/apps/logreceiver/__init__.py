"""
KillKrill Log Receiver - py4web Application
High-performance log ingestion service with Fleet integration
"""

import json
import os
from datetime import datetime

import redis
from prometheus_client import Counter, generate_latest
from py4web import DAL, HTTP, Field, action, request, response
from py4web.utils.cors import CORS

# Application name
__version__ = "1.0.0"

# Configuration
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://killkrill:killkrill123@postgres:5432/killkrill"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace("postgresql://", "postgres://")

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

# Create basic tables
try:
    db.define_table(
        "logs",
        Field("timestamp", "datetime", default=datetime.utcnow),
        Field("level", "string"),
        Field("message", "text"),
        Field("source", "string"),
        migrate=True,
    )
    db.commit()
except Exception as table_error:
    print(f"Note: Log table creation skipped - {table_error}")

print(f"✓ KillKrill Log Receiver py4web app initialized")

# Metrics
logs_received = Counter(
    "killkrill_logs_received_total", "Total logs received", ["level", "source"]
)
fleet_logs_received = Counter(
    "killkrill_fleet_logs_received_total", "Fleet logs received", ["stream_type"]
)
health_checks = Counter(
    "killkrill_log_receiver_health_checks_total", "Health checks", ["status"]
)


# Health check endpoint
@action("healthz")
@action.uses(CORS())
def healthz():
    """Health check endpoint"""
    try:
        # Test Redis
        redis_client.ping()

        # Test database
        db.logs.insert(level="info", message="health check", source="system")
        db.commit()

        health_checks.labels(status="ok").inc()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "killkrill-log-receiver",
            "components": {"database": "ok", "redis": "ok"},
        }
    except Exception as e:
        health_checks.labels(status="error").inc()
        response.status = 503
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Prometheus metrics endpoint
@action("metrics")
def metrics():
    """Prometheus metrics endpoint"""
    response.headers["Content-Type"] = "text/plain; version=0.0.4; charset=utf-8"
    return generate_latest()


# Log ingestion endpoint
@action("api/v1/logs", method=["POST"])
@action.uses(CORS())
def ingest_logs():
    """Simple log ingestion endpoint"""
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

        # Update metrics
        logs_received.labels(level=level, source=source).inc()

        return {
            "status": "accepted",
            "log_id": log_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        response.status = 500
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}


# Fleet Integration Endpoints
@action("fleet-logs", method=["POST"])
@action("api/kinesis/firehose", method=["POST"])  # Fleet expects this endpoint
@action.uses(CORS())
def ingest_fleet_logs():
    """Fleet osquery log ingestion endpoint (mimics AWS Kinesis)"""
    try:
        # Fleet sends logs as Kinesis-style records
        request_data = request.json or {}
        records = request_data.get("Records", [])

        if not records:
            # Handle direct Fleet log format
            records = [{"Data": json.dumps(request_data)}] if request_data else []

        processed_count = 0

        for record in records:
            try:
                # Extract log data from Kinesis record
                if isinstance(record.get("Data"), dict):
                    log_data = record["Data"]
                else:
                    log_data = json.loads(record.get("Data", "{}"))

                # Parse Fleet osquery log format
                timestamp = datetime.utcnow()
                if "unixTime" in log_data:
                    timestamp = datetime.fromtimestamp(log_data["unixTime"])
                elif "timestamp" in log_data:
                    try:
                        timestamp = datetime.fromisoformat(
                            log_data["timestamp"].replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Failed to parse timestamp: {e}")
                        timestamp = datetime.utcnow()

                # Determine log type and extract relevant information
                stream_name = request_data.get("StreamName", "unknown")
                source = f"fleet-{stream_name}"

                if "status" in log_data or stream_name == "fleet-status-logs":
                    # Fleet status logs
                    message = json.dumps(
                        {
                            "host_identifier": log_data.get(
                                "hostIdentifier", "unknown"
                            ),
                            "filename": log_data.get("filename", ""),
                            "message": log_data.get("message", ""),
                            "severity": log_data.get("severity", "INFO"),
                            "version": log_data.get("version", ""),
                            "unix_time": log_data.get("unixTime", 0),
                        }
                    )
                    level = (
                        "info"
                        if log_data.get("severity", "INFO") == "INFO"
                        else "error"
                    )
                    fleet_logs_received.labels(stream_type="status").inc()

                elif "snapshot" in log_data or stream_name == "fleet-result-logs":
                    # Fleet query results
                    message = json.dumps(
                        {
                            "host_identifier": log_data.get(
                                "hostIdentifier", "unknown"
                            ),
                            "calendar_time": log_data.get("calendarTime", ""),
                            "unix_time": log_data.get("unixTime", 0),
                            "epoch": log_data.get("epoch", 0),
                            "counter": log_data.get("counter", 0),
                            "name": log_data.get("name", ""),
                            "action": log_data.get("action", ""),
                            "snapshot": log_data.get("snapshot", []),
                            "columns": log_data.get("columns", {}),
                            "decorations": log_data.get("decorations", {}),
                        }
                    )
                    level = "info"
                    fleet_logs_received.labels(stream_type="results").inc()

                elif stream_name == "fleet-activity-logs":
                    # Fleet activity audit logs
                    message = json.dumps(
                        {
                            "activity_type": log_data.get("type", "unknown"),
                            "actor": log_data.get("actor_email", "system"),
                            "details": log_data.get("details", {}),
                            "timestamp": log_data.get("created_at", ""),
                        }
                    )
                    level = "info"
                    fleet_logs_received.labels(stream_type="activity").inc()

                else:
                    # Generic Fleet log
                    message = json.dumps(log_data)
                    level = "info"
                    fleet_logs_received.labels(stream_type="generic").inc()

                # Store in database
                log_id = db.logs.insert(
                    timestamp=timestamp, level=level, message=message, source=source
                )

                # Send to Redis stream for processing
                stream_data = {
                    "id": str(log_id),
                    "timestamp": timestamp.isoformat(),
                    "level": level,
                    "message": message,
                    "source": source,
                    "fleet_data": json.dumps(log_data),
                }
                redis_client.xadd("fleet-logs", stream_data)

                processed_count += 1

            except Exception as record_error:
                print(f"Error processing Fleet log record: {record_error}")
                continue

        db.commit()

        # Update overall metrics
        logs_received.labels(level="info", source="fleet").inc()

        # Return Kinesis-compatible response
        return {
            "FailedRecordCount": len(records) - processed_count,
            "RequestResponses": [
                {
                    "RecordId": f"fleet-{i}",
                    "Result": "Ok" if i < processed_count else "ProcessingFailed",
                }
                for i in range(len(records))
            ],
        }

    except Exception as e:
        print(f"Fleet log ingestion error: {e}")
        response.status = 500
        return {
            "FailedRecordCount": 1,
            "RequestResponses": [
                {"Result": "ProcessingFailed", "ErrorMessage": str(e)}
            ],
        }


# Main application index
@action("index")
def index():
    """Main application index"""
    log_count = db(db.logs).count()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill Log Receiver</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; }}
            .status {{ background: #f0f9ff; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            .endpoint {{ background: #f9fafb; padding: 1rem; border-radius: 4px; margin: 0.5rem 0; }}
            pre {{ background: #1f2937; color: #f9fafb; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>🐧 KillKrill Log Receiver</h1>
        <p>High-performance log ingestion service with Fleet integration</p>

        <div class="status">
            <h3>📊 Status</h3>
            <ul>
                <li><strong>Total logs received:</strong> {log_count:,}</li>
                <li><strong>Service:</strong> py4web application</li>
                <li><strong>Version:</strong> {__version__}</li>
            </ul>
        </div>

        <div class="endpoint">
            <h3>🔗 Available Endpoints</h3>
            <ul>
                <li><a href="/logreceiver/healthz">Health Check</a></li>
                <li><a href="/logreceiver/metrics">Prometheus Metrics</a></li>
                <li><strong>POST</strong> /logreceiver/api/v1/logs - Log ingestion</li>
                <li><strong>POST</strong> /logreceiver/fleet-logs - Fleet log ingestion</li>
            </ul>
        </div>

        <div class="endpoint">
            <h3>📝 Usage Example</h3>
            <pre>curl -X POST http://localhost:8081/logreceiver/api/v1/logs \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer PENG-DEMO-DEMO-DEMO-DEMO-DEMO" \\
  -d '{{"log_level": "info", "message": "Test log", "service_name": "test"}}'</pre>
        </div>

        <div class="endpoint">
            <h3>🛡️ Fleet Integration</h3>
            <p>This service accepts Fleet osquery logs via Kinesis-compatible endpoints:</p>
            <ul>
                <li><strong>Status Logs:</strong> fleet-status-logs stream</li>
                <li><strong>Query Results:</strong> fleet-result-logs stream</li>
                <li><strong>Activity Logs:</strong> fleet-activity-logs stream</li>
            </ul>
        </div>
    </body>
    </html>
    """


# Make sure the database connection is properly initialized when the module loads
try:
    db.logs.id  # Test table access
    print("✓ Database tables verified")
except Exception as e:
    print(f"⚠️ Database table issue: {e}")
