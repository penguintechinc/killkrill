"""
KillKrill API - AI Analysis Blueprint
Enterprise AI-powered analysis (license-gated)
"""

import uuid
from datetime import datetime

from quart import Blueprint, request, jsonify, g
import httpx
import structlog

from middleware.auth import require_auth, require_feature
from models.database import get_db
from config import get_config

logger = structlog.get_logger(__name__)

ai_analysis_bp = Blueprint('ai_analysis', __name__)


@ai_analysis_bp.route('/analyze', methods=['POST'])
@require_auth()
@require_feature('ai_analysis')
async def trigger_analysis():
    """
    Trigger AI analysis of metrics and logs (Enterprise feature)

    Request body (optional):
        analysis_type: Type of analysis (performance, security, capacity, anomaly)
        time_range: Time range for analysis (e.g., "24h", "7d")
    """
    data = await request.get_json() or {}

    analysis_id = f"analysis-{uuid.uuid4().hex[:12]}"
    analysis_type = data.get('analysis_type', 'comprehensive')

    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    # Create analysis record
    db.ai_analyses.insert(
        analysis_id=analysis_id,
        analysis_type=analysis_type,
        severity='pending',
        summary='Analysis in progress...',
    )
    db.commit()

    # TODO: Trigger async analysis via background task
    # For now, return immediately with pending status

    logger.info("ai_analysis_triggered", analysis_id=analysis_id, type=analysis_type)

    return jsonify({
        'analysis_id': analysis_id,
        'status': 'pending',
        'message': 'Analysis started. Check results endpoint for updates.'
    }), 202


@ai_analysis_bp.route('/results', methods=['GET'])
@require_auth()
@require_feature('ai_analysis')
async def list_analyses():
    """List AI analysis results"""
    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    limit = int(request.args.get('limit', 20))

    analyses = db(db.ai_analyses).select(
        orderby=~db.ai_analyses.timestamp,
        limitby=(0, limit)
    )

    return jsonify({
        'analyses': [{
            'analysis_id': a.analysis_id,
            'timestamp': a.timestamp.isoformat() if a.timestamp else None,
            'analysis_type': a.analysis_type,
            'severity': a.severity,
            'summary': a.summary,
            'is_acknowledged': a.is_acknowledged,
        } for a in analyses],
        'total': len(analyses)
    })


@ai_analysis_bp.route('/results/<analysis_id>', methods=['GET'])
@require_auth()
@require_feature('ai_analysis')
async def get_analysis(analysis_id: str):
    """Get specific analysis result"""
    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    analysis = db(db.ai_analyses.analysis_id == analysis_id).select().first()

    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404

    import json

    return jsonify({
        'analysis_id': analysis.analysis_id,
        'timestamp': analysis.timestamp.isoformat() if analysis.timestamp else None,
        'analysis_type': analysis.analysis_type,
        'severity': analysis.severity,
        'summary': analysis.summary,
        'recommendations': analysis.recommendations,
        'affected_components': json.loads(analysis.affected_components) if analysis.affected_components else [],
        'metrics_analyzed': json.loads(analysis.metrics_analyzed) if analysis.metrics_analyzed else {},
        'confidence_score': analysis.confidence_score,
        'is_acknowledged': analysis.is_acknowledged,
        'acknowledged_by': analysis.acknowledged_by,
        'acknowledged_at': analysis.acknowledged_at.isoformat() if analysis.acknowledged_at else None,
    })


@ai_analysis_bp.route('/results/<analysis_id>/acknowledge', methods=['PUT'])
@require_auth()
@require_feature('ai_analysis')
async def acknowledge_analysis(analysis_id: str):
    """Acknowledge an analysis result"""
    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    analysis = db(db.ai_analyses.analysis_id == analysis_id).select().first()

    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404

    username = g.auth.get('username', 'unknown')

    analysis.update_record(
        is_acknowledged=True,
        acknowledged_by=username,
        acknowledged_at=datetime.utcnow()
    )
    db.commit()

    logger.info("analysis_acknowledged", analysis_id=analysis_id, by=username)

    return jsonify({'message': 'Analysis acknowledged'})


@ai_analysis_bp.route('/config', methods=['GET'])
@require_auth()
@require_feature('ai_analysis')
async def get_ai_config():
    """Get AI analysis configuration"""
    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    # Return default config or from database
    return jsonify({
        'enabled': True,
        'auto_analyze_interval': '24h',
        'analysis_types': ['performance', 'security', 'capacity', 'anomaly'],
        'notification_threshold': 'medium',
    })
