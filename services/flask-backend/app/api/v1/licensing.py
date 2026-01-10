"""
KillKrill Flask Backend - Licensing Blueprint

Provides license management endpoints including license validation,
feature checking, and license status information via PenguinTech License Server.
"""

import os
from typing import Optional

import requests
import structlog
from flask import Blueprint, g, jsonify, request

logger = structlog.get_logger()

# Create licensing blueprint
licensing_bp = Blueprint("licensing", __name__, url_prefix="/licensing")

# License server configuration from environment
LICENSE_KEY = os.getenv("LICENSE_KEY", "")
LICENSE_SERVER_URL = os.getenv("LICENSE_SERVER_URL", "https://license.penguintech.io")
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "killkrill")


# ============================================================================
# Helper Functions
# ============================================================================


def get_license_headers() -> dict:
    """Get HTTP headers for license server API calls."""
    return {
        "Authorization": f"Bearer {LICENSE_KEY}",
        "Content-Type": "application/json",
    }


def validate_license_configured() -> Optional[tuple]:
    """
    Validate that license is properly configured.

    Returns error response tuple if not configured, None if valid.
    """
    if not LICENSE_KEY:
        logger.warning("licensing_not_configured", missing="LICENSE_KEY")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "License server not configured",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            503,
        )
    return None


# ============================================================================
# Routes
# ============================================================================


@licensing_bp.route("/", methods=["GET"])
def get_license_info():
    """
    Get current license information.

    Returns license details including tier, expiration, and features.
    """
    config_error = validate_license_configured()
    if config_error:
        return config_error

    try:
        response = requests.post(
            f"{LICENSE_SERVER_URL}/api/v2/validate",
            headers=get_license_headers(),
            json={"product": PRODUCT_NAME},
            timeout=5,
        )
        response.raise_for_status()

        license_data = response.json()
        logger.info("license_info_retrieved", tier=license_data.get("tier"))

        return (
            jsonify(
                {
                    "success": True,
                    "data": license_data,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except requests.RequestException as e:
        logger.error("license_server_error", error=str(e))
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to retrieve license information",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            502,
        )


@licensing_bp.route("/features", methods=["GET"])
def get_features():
    """
    Get available features and their entitlement status.

    Returns list of features with entitlement status and usage limits.
    """
    config_error = validate_license_configured()
    if config_error:
        return config_error

    feature_name = request.args.get("feature")

    try:
        payload = {"product": PRODUCT_NAME}
        if feature_name:
            payload["feature"] = feature_name

        response = requests.post(
            f"{LICENSE_SERVER_URL}/api/v2/features",
            headers=get_license_headers(),
            json=payload,
            timeout=5,
        )
        response.raise_for_status()

        features_data = response.json()
        logger.info(
            "features_retrieved", feature_count=len(features_data.get("features", []))
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": features_data,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except requests.RequestException as e:
        logger.error("license_server_error", error=str(e))
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to retrieve features",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            502,
        )


@licensing_bp.route("/status", methods=["GET"])
def get_license_status():
    """
    Get license status summary.

    Returns concise license status, expiration, and tier information.
    """
    config_error = validate_license_configured()
    if config_error:
        return config_error

    try:
        response = requests.post(
            f"{LICENSE_SERVER_URL}/api/v2/validate",
            headers=get_license_headers(),
            json={"product": PRODUCT_NAME},
            timeout=5,
        )
        response.raise_for_status()

        license_data = response.json()

        status = {
            "valid": True,
            "customer": license_data.get("customer", "Unknown"),
            "tier": license_data.get("tier", "community"),
            "expires_at": license_data.get("expires_at"),
            "issued_at": license_data.get("issued_at"),
        }

        logger.info("license_status_retrieved", tier=status.get("tier"))

        return (
            jsonify(
                {
                    "success": True,
                    "data": status,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except requests.RequestException as e:
        logger.error("license_server_error", error=str(e))
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to retrieve license status",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            502,
        )


@licensing_bp.route("/validate", methods=["POST"])
def validate_license():
    """
    Validate a license key.

    Accepts a license key in the request body and validates it against
    the PenguinTech License Server.
    """
    try:
        payload = request.get_json() or {}
        license_key = payload.get("license_key")

        if not license_key:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "license_key is required",
                        "correlation_id": g.get("correlation_id"),
                    }
                ),
                400,
            )

        # Validate license key format
        import re

        if not re.match(
            r"^PENG-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$",
            license_key,
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid license key format",
                        "correlation_id": g.get("correlation_id"),
                    }
                ),
                400,
            )

        # Validate against license server
        headers = {
            "Authorization": f"Bearer {license_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{LICENSE_SERVER_URL}/api/v2/validate",
            headers=headers,
            json={"product": PRODUCT_NAME},
            timeout=5,
        )
        response.raise_for_status()

        license_data = response.json()

        validation_result = {
            "valid": True,
            "customer": license_data.get("customer"),
            "tier": license_data.get("tier"),
            "expires_at": license_data.get("expires_at"),
            "features_count": len(license_data.get("features", [])),
        }

        logger.info("license_validated", tier=validation_result.get("tier"))

        return (
            jsonify(
                {
                    "success": True,
                    "data": validation_result,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except requests.RequestException as e:
        logger.error("license_validation_failed", error=str(e))
        return (
            jsonify(
                {
                    "success": False,
                    "error": "License validation failed",
                    "details": str(e),
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            400,
        )


__all__ = ["licensing_bp"]
