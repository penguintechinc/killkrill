"""
KillKrill Flask Backend - Sensors API Blueprint
Endpoints for sensor agents, checks, and results with Pydantic validation.
"""

from datetime import datetime

from app.api.v1.schemas import (
    APIResponse, ErrorResponse, SensorAgentCreate, SensorCheckCreate,
    SensorResultSubmit,
)
from app.models.database import get_pydal_connection
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

sensors_bp = Blueprint("sensors", __name__)


# ============================================================================
# Agent Endpoints
# ============================================================================


@sensors_bp.route("/agents", methods=["GET", "POST"])
def agents_list_create():
    """GET: List all agents. POST: Create new agent."""
    db = get_pydal_connection()

    if request.method == "GET":
        agents = db(db.sensor_agents).select().as_list()
        return jsonify(APIResponse(success=True, data=agents).model_dump()), 200

    # POST
    try:
        data = SensorAgentCreate(**request.json)
        import hashlib

        api_key = hashlib.sha256(f"{data.name}{datetime.utcnow()}".encode()).hexdigest()
        agent_id = db.sensor_agents.insert(
            agent_id=data.name.lower().replace(" ", "_"),
            name=data.name,
            hostname="",
            ip_address=request.remote_addr,
            api_key_hash=api_key,
            metadata={},
        )
        db.commit()

        agent = db.sensor_agents[agent_id].as_dict()
        return jsonify(APIResponse(success=True, data=agent).model_dump()), 201
    except ValidationError as e:
        return (
            jsonify(ErrorResponse(error=str(e), code="VALIDATION_ERROR").model_dump()),
            400,
        )


@sensors_bp.route("/agents/<int:id>", methods=["GET", "DELETE"])
def agent_detail(id):
    """GET: Get agent by ID. DELETE: Delete agent."""
    db = get_pydal_connection()
    agent = db.sensor_agents[id]

    if not agent:
        return (
            jsonify(
                ErrorResponse(error="Agent not found", code="NOT_FOUND").model_dump()
            ),
            404,
        )

    if request.method == "GET":
        return (
            jsonify(APIResponse(success=True, data=agent.as_dict()).model_dump()),
            200,
        )

    # DELETE
    del db.sensor_agents[id]
    db.commit()
    return jsonify(APIResponse(success=True, message="Agent deleted").model_dump()), 200


@sensors_bp.route("/agents/<int:id>/heartbeat", methods=["POST"])
def agent_heartbeat(id):
    """POST: Update agent heartbeat."""
    db = get_pydal_connection()
    agent = db.sensor_agents[id]

    if not agent:
        return (
            jsonify(
                ErrorResponse(error="Agent not found", code="NOT_FOUND").model_dump()
            ),
            404,
        )

    db(db.sensor_agents.id == id).update(last_heartbeat=datetime.utcnow())
    db.commit()

    return (
        jsonify(APIResponse(success=True, message="Heartbeat recorded").model_dump()),
        200,
    )


# ============================================================================
# Check Endpoints
# ============================================================================


@sensors_bp.route("/checks", methods=["GET", "POST"])
def checks_list_create():
    """GET: List all checks. POST: Create new check."""
    db = get_pydal_connection()

    if request.method == "GET":
        checks = db(db.sensor_checks).select().as_list()
        return jsonify(APIResponse(success=True, data=checks).model_dump()), 200

    # POST
    try:
        data = SensorCheckCreate(**request.json)
        check_id = db.sensor_checks.insert(
            name=data.name,
            check_type=data.check_type.value,
            target=data.target,
            port=data.port,
            interval=data.interval,
            timeout=data.timeout,
            is_active=data.enabled,
        )
        db.commit()

        check = db.sensor_checks[check_id].as_dict()
        return jsonify(APIResponse(success=True, data=check).model_dump()), 201
    except ValidationError as e:
        return (
            jsonify(ErrorResponse(error=str(e), code="VALIDATION_ERROR").model_dump()),
            400,
        )


@sensors_bp.route("/checks/<int:id>", methods=["GET", "PUT", "DELETE"])
def check_detail(id):
    """GET: Get check. PUT: Update check. DELETE: Delete check."""
    db = get_pydal_connection()
    check = db.sensor_checks[id]

    if not check:
        return (
            jsonify(
                ErrorResponse(error="Check not found", code="NOT_FOUND").model_dump()
            ),
            404,
        )

    if request.method == "GET":
        return (
            jsonify(APIResponse(success=True, data=check.as_dict()).model_dump()),
            200,
        )

    if request.method == "PUT":
        try:
            data = SensorCheckCreate(**request.json)
            db(db.sensor_checks.id == id).update(
                name=data.name,
                check_type=data.check_type.value,
                target=data.target,
                port=data.port,
                interval=data.interval,
                timeout=data.timeout,
                is_active=data.enabled,
            )
            db.commit()
            updated_check = db.sensor_checks[id].as_dict()
            return (
                jsonify(APIResponse(success=True, data=updated_check).model_dump()),
                200,
            )
        except ValidationError as e:
            return (
                jsonify(
                    ErrorResponse(error=str(e), code="VALIDATION_ERROR").model_dump()
                ),
                400,
            )

    # DELETE
    del db.sensor_checks[id]
    db.commit()
    return jsonify(APIResponse(success=True, message="Check deleted").model_dump()), 200


# ============================================================================
# Result Endpoints
# ============================================================================


@sensors_bp.route("/results", methods=["GET", "POST"])
def results_list_submit():
    """GET: List results. POST: Submit check result."""
    db = get_pydal_connection()

    if request.method == "GET":
        limit = request.args.get("limit", 100, type=int)
        results = (
            db(db.sensor_results)
            .select(limitby=(0, limit), orderby=~db.sensor_results.created_at)
            .as_list()
        )
        return jsonify(APIResponse(success=True, data=results).model_dump()), 200

    # POST
    try:
        data = SensorResultSubmit(**request.json)
        result_id = db.sensor_results.insert(
            check_id=int(data.check_id),
            agent_id=1,  # TODO: Get from auth context
            status=data.status,
            response_time_ms=int(data.response_time),
            error_message=data.message,
        )
        db.commit()

        result = db.sensor_results[result_id].as_dict()
        return jsonify(APIResponse(success=True, data=result).model_dump()), 201
    except ValidationError as e:
        return (
            jsonify(ErrorResponse(error=str(e), code="VALIDATION_ERROR").model_dump()),
            400,
        )


@sensors_bp.route("/status", methods=["GET"])
def system_status():
    """GET: Overall system status."""
    db = get_pydal_connection()

    total_agents = db(db.sensor_agents).count()
    active_agents = db(db.sensor_agents.is_active == True).count()
    total_checks = db(db.sensor_checks).count()
    active_checks = db(db.sensor_checks.is_active == True).count()

    status = {
        "agents": {"total": total_agents, "active": active_agents},
        "checks": {"total": total_checks, "active": active_checks},
        "timestamp": datetime.utcnow().isoformat(),
    }

    return jsonify(APIResponse(success=True, data=status).model_dump()), 200


@sensors_bp.route("/config/<int:agent_id>", methods=["GET"])
def agent_config(agent_id):
    """GET: Get agent configuration."""
    db = get_pydal_connection()
    agent = db.sensor_agents[agent_id]

    if not agent:
        return (
            jsonify(
                ErrorResponse(error="Agent not found", code="NOT_FOUND").model_dump()
            ),
            404,
        )

    checks = db(db.sensor_checks.is_active == True).select().as_list()

    config = {
        "agent": agent.as_dict(),
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }

    return jsonify(APIResponse(success=True, data=config).model_dump()), 200
