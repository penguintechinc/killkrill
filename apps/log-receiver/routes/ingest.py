"""
KillKrill Log Receiver - Log Ingestion Endpoint
"""

from datetime import datetime
from quart import Blueprint, request, jsonify, current_app
from prometheus_client import Counter
import structlog

from shared.receiver_client import AuthenticationError, ConnectionError

logger = structlog.get_logger(__name__)

ingest_bp = Blueprint('ingest', __name__)

# Metrics
logs_received = Counter('killkrill_logs_received_total', 'Total logs received', ['level'])


@ingest_bp.route('/api/v1/logs', methods=['POST'])
async def ingest_logs():
    """Log ingestion endpoint with ReceiverClient submission"""
    try:
        log_data = await request.get_json()

        # Basic validation
        if not log_data:
            return jsonify({'error': 'No JSON data provided'}), 400

        db = current_app.db
        redis_client = current_app.redis_client
        receiver_client = current_app.receiver_client

        # Extract log fields
        timestamp = log_data.get('timestamp')
        if timestamp:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            timestamp = datetime.utcnow()

        level = log_data.get('log_level', log_data.get('level', 'info'))
        message = log_data.get('message', str(log_data))
        source = log_data.get('service_name', log_data.get('source', 'unknown'))

        # Store in database
        log_id = db.logs.insert(
            timestamp=timestamp,
            level=level,
            message=message,
            source=source
        )
        db.commit()

        # Send to Redis stream
        stream_data = {
            'id': str(log_id),
            'timestamp': timestamp.isoformat(),
            'level': level,
            'message': message,
            'source': source
        }
        redis_client.xadd('logs', stream_data)

        # Submit to backend via ReceiverClient (gRPC with REST fallback)
        if receiver_client:
            try:
                log_payload = {
                    'timestamp': timestamp.isoformat(),
                    'level': level,
                    'message': message,
                    'source': source
                }
                await receiver_client.submit_logs([log_payload])
                logger.info("log_submitted", log_id=log_id)
            except (AuthenticationError, ConnectionError) as e:
                # Log submission error but continue (non-fatal)
                logger.warning("receiver_submission_error", error=str(e))

        # Update metrics
        logs_received.labels(level=level).inc()

        return jsonify({
            'status': 'accepted',
            'log_id': log_id,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error("log_ingestion_error", error=str(e))
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
