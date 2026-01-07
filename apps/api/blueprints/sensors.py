"""
KillKrill API - Sensors Blueprint
External sensor agent management and uptime monitoring
"""

import hashlib
import uuid
from datetime import datetime

import structlog
from middleware.auth import (generate_api_key, hash_api_key, require_auth,
                             require_role)
from models.database import get_db
from quart import Blueprint, g, jsonify, request
from services.redis_service import cache

logger = structlog.get_logger(__name__)

sensors_bp = Blueprint("sensors", __name__)


# ============== Sensor Agent Management ==============


@sensors_bp.route("/", methods=["GET"])
@require_auth()
async def list_sensors():
    """List all sensor agents"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    sensors = db(db.sensor_agents).select(orderby=~db.sensor_agents.created_at)

    return jsonify(
        {
            "sensors": [
                {
                    "agent_id": s.agent_id,
                    "name": s.name,
                    "location": s.location,
                    "is_active": s.is_active,
                    "last_heartbeat": (
                        s.last_heartbeat.isoformat() if s.last_heartbeat else None
                    ),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sensors
            ],
            "total": len(sensors),
        }
    )


@sensors_bp.route("/", methods=["POST"])
@require_auth()
@require_role(["admin"])
async def create_sensor():
    """
    Register a new sensor agent

    Request body:
        name: Sensor name
        location: Location identifier (e.g., "AWS-us-east-1", "Home-NYC")
    """
    data = await request.get_json()

    if not data or not data.get("name"):
        return jsonify({"error": "Sensor name required"}), 400

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Generate unique agent ID and API key
    agent_id = f"sensor-{uuid.uuid4().hex[:12]}"
    api_key = generate_api_key(48)
    api_key_hash = hash_api_key(api_key)

    db.sensor_agents.insert(
        agent_id=agent_id,
        name=data.get("name"),
        location=data.get("location", "default"),
        api_key_hash=api_key_hash,
        is_active=True,
    )
    db.commit()

    logger.info("sensor_created", agent_id=agent_id, by=g.auth.get("user_id"))

    return (
        jsonify(
            {
                "agent_id": agent_id,
                "api_key": api_key,  # Only returned once
                "name": data.get("name"),
                "location": data.get("location", "default"),
                "message": "Store this API key securely - it cannot be retrieved later",
            }
        ),
        201,
    )


@sensors_bp.route("/<agent_id>", methods=["GET"])
@require_auth()
async def get_sensor(agent_id: str):
    """Get sensor agent details"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    sensor = db(db.sensor_agents.agent_id == agent_id).select().first()

    if not sensor:
        return jsonify({"error": "Sensor not found"}), 404

    # Get recent results
    results = db(db.sensor_results.agent_id == agent_id).select(
        orderby=~db.sensor_results.timestamp, limitby=(0, 10)
    )

    return jsonify(
        {
            "agent_id": sensor.agent_id,
            "name": sensor.name,
            "location": sensor.location,
            "is_active": sensor.is_active,
            "last_heartbeat": (
                sensor.last_heartbeat.isoformat() if sensor.last_heartbeat else None
            ),
            "created_at": sensor.created_at.isoformat() if sensor.created_at else None,
            "recent_results": [
                {
                    "check_id": r.check_id,
                    "status": r.status,
                    "response_time_ms": r.response_time_ms,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in results
            ],
        }
    )


@sensors_bp.route("/<agent_id>", methods=["DELETE"])
@require_auth()
@require_role(["admin"])
async def delete_sensor(agent_id: str):
    """Delete/deactivate sensor agent"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    result = db(db.sensor_agents.agent_id == agent_id).update(is_active=False)
    db.commit()

    if not result:
        return jsonify({"error": "Sensor not found"}), 404

    logger.info("sensor_deleted", agent_id=agent_id, by=g.auth.get("user_id"))

    return jsonify({"message": "Sensor deactivated"})


@sensors_bp.route("/<agent_id>/heartbeat", methods=["POST"])
async def sensor_heartbeat(agent_id: str):
    """
    Sensor agent heartbeat (authenticated via API key)
    """
    # Authenticate via API key header
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "API key required"}), 401

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    api_key_hash = hash_api_key(api_key)
    sensor = (
        db(
            (db.sensor_agents.agent_id == agent_id)
            & (db.sensor_agents.api_key_hash == api_key_hash)
            & (db.sensor_agents.is_active == True)
        )
        .select()
        .first()
    )

    if not sensor:
        return jsonify({"error": "Invalid sensor or API key"}), 401

    sensor.update_record(last_heartbeat=datetime.utcnow())
    db.commit()

    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


# ============== Check Configuration ==============


@sensors_bp.route("/checks", methods=["GET"])
@require_auth()
async def list_checks():
    """List all configured checks"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    checks = db(db.sensor_checks).select(orderby=db.sensor_checks.name)

    return jsonify(
        {
            "checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "check_type": c.check_type,
                    "target": c.target,
                    "port": c.port,
                    "path": c.path,
                    "interval_seconds": c.interval_seconds,
                    "is_active": c.is_active,
                }
                for c in checks
            ],
            "total": len(checks),
        }
    )


@sensors_bp.route("/checks", methods=["POST"])
@require_auth()
@require_role(["admin"])
async def create_check():
    """
    Create a new check configuration

    Request body:
        name: Check name
        check_type: tcp, http, https, dns
        target: Hostname or IP
        port: Port number (optional for dns)
        path: HTTP path (optional)
        expected_status: Expected HTTP status code (optional)
        timeout_ms: Timeout in milliseconds
        interval_seconds: Check interval
        headers: JSON object of HTTP headers (optional)
    """
    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["name", "check_type", "target"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    if data.get("check_type") not in ["tcp", "http", "https", "dns"]:
        return jsonify({"error": "Invalid check_type"}), 400

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    check_id = f"check-{uuid.uuid4().hex[:12]}"

    import json

    headers_json = json.dumps(data.get("headers", {})) if data.get("headers") else None

    db.sensor_checks.insert(
        check_id=check_id,
        name=data.get("name"),
        check_type=data.get("check_type"),
        target=data.get("target"),
        port=data.get("port"),
        path=data.get("path"),
        expected_status=data.get("expected_status", 200),
        timeout_ms=data.get("timeout_ms", 5000),
        interval_seconds=data.get("interval_seconds", 60),
        headers=headers_json,
        is_active=True,
    )
    db.commit()

    logger.info("check_created", check_id=check_id, by=g.auth.get("user_id"))

    return jsonify({"check_id": check_id, "message": "Check created"}), 201


@sensors_bp.route("/checks/<check_id>", methods=["GET"])
@require_auth()
async def get_check(check_id: str):
    """Get check configuration and recent results"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    check = db(db.sensor_checks.check_id == check_id).select().first()

    if not check:
        return jsonify({"error": "Check not found"}), 404

    # Get recent results from all sensors
    results = db(db.sensor_results.check_id == check_id).select(
        orderby=~db.sensor_results.timestamp, limitby=(0, 50)
    )

    import json

    return jsonify(
        {
            "check_id": check.check_id,
            "name": check.name,
            "check_type": check.check_type,
            "target": check.target,
            "port": check.port,
            "path": check.path,
            "expected_status": check.expected_status,
            "timeout_ms": check.timeout_ms,
            "interval_seconds": check.interval_seconds,
            "headers": json.loads(check.headers) if check.headers else {},
            "is_active": check.is_active,
            "recent_results": [
                {
                    "agent_id": r.agent_id,
                    "status": r.status,
                    "response_time_ms": r.response_time_ms,
                    "status_code": r.status_code,
                    "error_message": r.error_message,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in results
            ],
        }
    )


@sensors_bp.route("/checks/<check_id>", methods=["PUT"])
@require_auth()
@require_role(["admin"])
async def update_check(check_id: str):
    """Update check configuration"""
    data = await request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    check = db(db.sensor_checks.check_id == check_id).select().first()
    if not check:
        return jsonify({"error": "Check not found"}), 404

    update_fields = {}
    allowed_fields = [
        "name",
        "target",
        "port",
        "path",
        "expected_status",
        "timeout_ms",
        "interval_seconds",
        "is_active",
    ]

    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]

    if data.get("headers"):
        import json

        update_fields["headers"] = json.dumps(data["headers"])

    if update_fields:
        check.update_record(**update_fields)
        db.commit()

    return jsonify({"message": "Check updated"})


@sensors_bp.route("/checks/<check_id>", methods=["DELETE"])
@require_auth()
@require_role(["admin"])
async def delete_check(check_id: str):
    """Delete check configuration"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    result = db(db.sensor_checks.check_id == check_id).delete()
    db.commit()

    if not result:
        return jsonify({"error": "Check not found"}), 404

    return jsonify({"message": "Check deleted"})


# ============== Results ==============


@sensors_bp.route("/results", methods=["POST"])
async def submit_results():
    """
    Submit check results from sensor agent
    Authenticated via X-API-Key header
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "API key required"}), 401

    data = await request.get_json()
    if not data:
        return jsonify({"error": "Results data required"}), 400

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Validate sensor
    api_key_hash = hash_api_key(api_key)
    sensor = (
        db(
            (db.sensor_agents.api_key_hash == api_key_hash)
            & (db.sensor_agents.is_active == True)
        )
        .select()
        .first()
    )

    if not sensor:
        return jsonify({"error": "Invalid API key"}), 401

    agent_id = sensor.agent_id

    # Process results (can be single result or batch)
    results = data.get("results", [data]) if "results" in data else [data]

    for result in results:
        db.sensor_results.insert(
            agent_id=agent_id,
            check_id=result.get("check_id"),
            status=result.get("status", "unknown"),
            response_time_ms=result.get("response_time_ms"),
            status_code=result.get("status_code"),
            error_message=result.get("error_message"),
            ssl_expiry=result.get("ssl_expiry"),
            ssl_valid=result.get("ssl_valid"),
        )

    # Update heartbeat
    sensor.update_record(last_heartbeat=datetime.utcnow())
    db.commit()

    # Broadcast via WebSocket
    # TODO: Implement WebSocket broadcast

    logger.debug("results_submitted", agent_id=agent_id, count=len(results))

    return jsonify({"status": "ok", "processed": len(results)})


@sensors_bp.route("/results", methods=["GET"])
@require_auth()
async def query_results():
    """Query check results with filters"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Parse query params
    check_id = request.args.get("check_id")
    agent_id = request.args.get("agent_id")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 100))

    query = db.sensor_results

    if check_id:
        query = query.check_id == check_id
    if agent_id:
        query = (
            query.agent_id == agent_id
            if not check_id
            else query & (db.sensor_results.agent_id == agent_id)
        )
    if status:
        query = (
            query.status == status
            if not check_id and not agent_id
            else query & (db.sensor_results.status == status)
        )

    if check_id or agent_id or status:
        results = db(query).select(
            orderby=~db.sensor_results.timestamp, limitby=(0, limit)
        )
    else:
        results = db(db.sensor_results).select(
            orderby=~db.sensor_results.timestamp, limitby=(0, limit)
        )

    return jsonify(
        {
            "results": [
                {
                    "agent_id": r.agent_id,
                    "check_id": r.check_id,
                    "status": r.status,
                    "response_time_ms": r.response_time_ms,
                    "status_code": r.status_code,
                    "error_message": r.error_message,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in results
            ],
            "total": len(results),
        }
    )


@sensors_bp.route("/status", methods=["GET"])
@require_auth()
async def get_status_summary():
    """Get overall uptime status summary"""
    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Get all active checks
    checks = db(db.sensor_checks.is_active == True).select()

    status_summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_checks": len(checks),
        "checks_up": 0,
        "checks_down": 0,
        "checks_unknown": 0,
        "checks": [],
    }

    for check in checks:
        # Get latest result for this check
        latest = (
            db(db.sensor_results.check_id == check.check_id)
            .select(orderby=~db.sensor_results.timestamp, limitby=(0, 1))
            .first()
        )

        check_status = {
            "check_id": check.check_id,
            "name": check.name,
            "target": check.target,
            "status": latest.status if latest else "unknown",
            "last_check": (
                latest.timestamp.isoformat() if latest and latest.timestamp else None
            ),
            "response_time_ms": latest.response_time_ms if latest else None,
        }

        if latest:
            if latest.status == "up":
                status_summary["checks_up"] += 1
            elif latest.status in ["down", "error", "timeout"]:
                status_summary["checks_down"] += 1
            else:
                status_summary["checks_unknown"] += 1
        else:
            status_summary["checks_unknown"] += 1

        status_summary["checks"].append(check_status)

    return jsonify(status_summary)


@sensors_bp.route("/config/<agent_id>", methods=["GET"])
async def get_agent_config(agent_id: str):
    """
    Get checks assigned to a sensor agent
    Called by sensor agents to fetch their configuration
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "API key required"}), 401

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Validate sensor
    api_key_hash = hash_api_key(api_key)
    sensor = (
        db(
            (db.sensor_agents.agent_id == agent_id)
            & (db.sensor_agents.api_key_hash == api_key_hash)
            & (db.sensor_agents.is_active == True)
        )
        .select()
        .first()
    )

    if not sensor:
        return jsonify({"error": "Invalid sensor or API key"}), 401

    # Get all active checks (all sensors run all checks)
    checks = db(db.sensor_checks.is_active == True).select()

    import json

    return jsonify(
        {
            "agent_id": agent_id,
            "checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "check_type": c.check_type,
                    "target": c.target,
                    "port": c.port,
                    "path": c.path,
                    "expected_status": c.expected_status,
                    "timeout_ms": c.timeout_ms,
                    "interval_seconds": c.interval_seconds,
                    "headers": json.loads(c.headers) if c.headers else {},
                }
                for c in checks
            ],
        }
    )
