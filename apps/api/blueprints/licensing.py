"""
KillKrill API - Licensing Blueprint
License management and feature information
"""

import structlog
from middleware.auth import require_auth
from quart import Blueprint, jsonify
from services.license_service import (
    get_all_features, get_license_info, is_license_valid,
)

logger = structlog.get_logger(__name__)

licensing_bp = Blueprint("licensing", __name__)


@licensing_bp.route("/", methods=["GET"])
@require_auth()
async def get_license():
    """Get current license information"""
    info = await get_license_info()

    if not info:
        return jsonify({"valid": False, "message": "No license configured"})

    return jsonify(
        {
            "valid": info.get("valid", False),
            "customer": info.get("customer"),
            "tier": info.get("tier"),
            "expires_at": info.get("expires_at"),
            "limits": info.get("limits", {}),
        }
    )


@licensing_bp.route("/features", methods=["GET"])
@require_auth()
async def get_features():
    """Get all feature entitlements"""
    features = await get_all_features()

    return jsonify({"features": features, "license_valid": is_license_valid()})


@licensing_bp.route("/status", methods=["GET"])
@require_auth()
async def license_status():
    """Get license status summary"""
    info = await get_license_info()
    features = await get_all_features()

    enabled_features = [f for f, enabled in features.items() if enabled]
    disabled_features = [f for f, enabled in features.items() if not enabled]

    return jsonify(
        {
            "valid": is_license_valid(),
            "tier": info.get("tier") if info else None,
            "customer": info.get("customer") if info else None,
            "features_enabled": len(enabled_features),
            "features_disabled": len(disabled_features),
            "enabled": enabled_features,
            "disabled": disabled_features,
        }
    )
