"""
KillKrill API - Fleet Blueprint
Fleet device management integration
"""

from datetime import datetime

import httpx
import structlog
from middleware.auth import require_auth, require_feature
from quart import Blueprint, jsonify, request

from config import get_config

logger = structlog.get_logger(__name__)

fleet_bp = Blueprint("fleet", __name__)


@fleet_bp.route("/status", methods=["GET"])
@require_auth()
async def fleet_status():
    """Get Fleet server status"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.FLEET_SERVER_URL}/api/v1/fleet/version",
                headers={"Authorization": f"Bearer {config.FLEET_API_TOKEN}"},
                timeout=10.0,
            )
            return jsonify(
                response.json() if response.status_code == 200 else {"status": "error"}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@fleet_bp.route("/hosts", methods=["GET"])
@require_auth()
async def list_hosts():
    """List Fleet hosts"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.FLEET_SERVER_URL}/api/v1/fleet/hosts",
                headers={"Authorization": f"Bearer {config.FLEET_API_TOKEN}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return jsonify(
                    {
                        "hosts": data.get("hosts", []),
                        "total": len(data.get("hosts", [])),
                    }
                )
            else:
                return jsonify({"hosts": [], "total": 0})
    except Exception as e:
        logger.error("fleet_hosts_error", error=str(e))
        return jsonify({"error": str(e)}), 503


@fleet_bp.route("/hosts/<int:host_id>", methods=["GET"])
@require_auth()
async def get_host(host_id: int):
    """Get Fleet host details"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.FLEET_SERVER_URL}/api/v1/fleet/hosts/{host_id}",
                headers={"Authorization": f"Bearer {config.FLEET_API_TOKEN}"},
                timeout=10.0,
            )
            return jsonify(
                response.json()
                if response.status_code == 200
                else {"error": "Host not found"}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@fleet_bp.route("/queries", methods=["GET"])
@require_auth()
async def list_queries():
    """List Fleet queries"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.FLEET_SERVER_URL}/api/v1/fleet/queries",
                headers={"Authorization": f"Bearer {config.FLEET_API_TOKEN}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return jsonify(
                    {
                        "queries": data.get("queries", []),
                        "total": len(data.get("queries", [])),
                    }
                )
            else:
                return jsonify({"queries": [], "total": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@fleet_bp.route("/queries/run", methods=["POST"])
@require_auth()
@require_feature("fleet_live_query")
async def run_query():
    """Run a live query on Fleet hosts"""
    config = get_config()
    data = await request.get_json()

    if not data or not data.get("query"):
        return jsonify({"error": "Query required"}), 400

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.FLEET_SERVER_URL}/api/v1/fleet/queries/run",
                headers={"Authorization": f"Bearer {config.FLEET_API_TOKEN}"},
                json={
                    "query": data.get("query"),
                    "selected": {"hosts": data.get("host_ids", [])},
                },
                timeout=60.0,
            )
            return jsonify(
                response.json()
                if response.status_code == 200
                else {"error": "Query failed"}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@fleet_bp.route("/policies", methods=["GET"])
@require_auth()
async def list_policies():
    """List Fleet policies"""
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.FLEET_SERVER_URL}/api/v1/fleet/global/policies",
                headers={"Authorization": f"Bearer {config.FLEET_API_TOKEN}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return jsonify(
                    {
                        "policies": data.get("policies", []),
                        "total": len(data.get("policies", [])),
                    }
                )
            else:
                return jsonify({"policies": [], "total": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 503
