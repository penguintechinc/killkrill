"""Metrics ingestion endpoint."""
import json
from datetime import datetime
from quart import Blueprint, request, jsonify, current_app
import structlog

logger = structlog.get_logger(__name__)
bp = Blueprint('ingest', __name__)


@bp.route('/api/v1/metrics', methods=['POST'])
async def receive_metrics():
    """Metrics ingestion endpoint with gRPC/REST fallback submission."""
    try:
        data = await request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        # Process metric
        metric_name = data.get('name', 'unknown')
        metric_type = data.get('type', 'gauge')
        metric_value = float(data.get('value', 0))
        labels = json.dumps(data.get('labels', {}))
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
        timestamp = datetime.utcnow()

        # Store in database
        current_app.db.received_metrics.insert(
            metric_name=metric_name,
            metric_type=metric_type,
            metric_value=metric_value,
            labels=labels,
            timestamp=timestamp,
            source_ip=client_ip
        )
        current_app.db.commit()

        # Send to Redis stream
        stream_data = {
            'metric_name': metric_name,
            'metric_type': metric_type,
            'metric_value': str(metric_value),
            'labels': labels,
            'timestamp': timestamp.isoformat(),
            'client_ip': client_ip
        }
        await current_app.redis_client.xadd('metrics:raw', stream_data)

        # Submit via ReceiverClient with retry logic
        if current_app.receiver_client:
            try:
                metric_entry = {
                    'name': metric_name,
                    'type': metric_type,
                    'value': metric_value,
                    'labels': json.loads(labels),
                    'timestamp': timestamp.isoformat(),
                    'source': client_ip
                }
                await current_app.receiver_client.submit_metrics([metric_entry])
                logger.info("metric_submitted", metric_name=metric_name)
            except Exception as e:
                logger.error("metric_submission_failed", error=str(e), metric_name=metric_name)
                # Don't fail the request - metric is already stored locally

        # Update counter
        current_app.received_metrics_counter.labels(metric_type=metric_type).inc()

        return jsonify({
            'status': 'success',
            'timestamp': timestamp.isoformat()
        }), 200

    except Exception as e:
        logger.error("metrics_ingestion_error", error=str(e))
        return jsonify({'error': str(e)}), 500
