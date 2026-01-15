"""
KillKrill API - License Service
PenguinTech License Server integration
"""

from datetime import datetime
from typing import Any, Dict, Optional

import httpx
import structlog
from quart import Quart

from config import get_config
from services.redis_service import cache

logger = structlog.get_logger(__name__)

# Global license state
_license_info: Optional[Dict[str, Any]] = None
_license_valid: bool = False


async def init_license(app: Quart) -> None:
    """Initialize license validation"""
    global _license_info, _license_valid

    config = app.killkrill_config

    if not config.LICENSE_KEY:
        logger.warning("no_license_key", message="Running without license validation")
        _license_valid = False
        return

    try:
        validation = await validate_license(config.LICENSE_KEY, config.PRODUCT_NAME)

        if validation.get("valid"):
            _license_info = validation
            _license_valid = True
            logger.info(
                "license_validated",
                customer=validation.get("customer"),
                tier=validation.get("tier"),
                expires=validation.get("expires_at"),
            )
        else:
            _license_valid = False
            logger.error("license_invalid", message=validation.get("message"))

    except Exception as e:
        logger.error("license_init_failed", error=str(e))
        _license_valid = False


async def validate_license(license_key: str, product: str) -> Dict[str, Any]:
    """
    Validate license with PenguinTech License Server

    Args:
        license_key: License key (PENG-XXXX-XXXX-XXXX-XXXX-ABCD)
        product: Product identifier

    Returns:
        Validation response dict
    """
    config = get_config()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.LICENSE_SERVER_URL}/api/v2/validate",
                headers={"Authorization": f"Bearer {license_key}"},
                json={"product": product},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "valid": data.get("valid", False),
                    "customer": data.get("customer"),
                    "tier": data.get("tier"),
                    "expires_at": data.get("expires_at"),
                    "features": data.get("features", []),
                    "limits": data.get("limits", {}),
                    "message": data.get("message"),
                }
            else:
                return {
                    "valid": False,
                    "message": f"Validation failed: HTTP {response.status_code}",
                }

    except httpx.TimeoutException:
        return {"valid": False, "message": "License server timeout"}
    except Exception as e:
        return {"valid": False, "message": str(e)}


async def check_feature(feature_name: str, use_cache: bool = True) -> bool:
    """
    Check if a feature is entitled

    Args:
        feature_name: Name of the feature to check
        use_cache: Whether to use cached result

    Returns:
        True if feature is entitled, False otherwise
    """
    global _license_info

    # Check cache first
    if use_cache:
        cached = await cache.get(f"feature:{feature_name}")
        if cached is not None:
            return cached == "true"

    # Check license info
    if not _license_info:
        return False

    features = _license_info.get("features", [])
    for feature in features:
        if feature.get("name") == feature_name:
            entitled = feature.get("entitled", False)

            # Cache the result for 5 minutes
            await cache.set(
                f"feature:{feature_name}", "true" if entitled else "false", ttl=300
            )

            return entitled

    return False


async def get_license_info() -> Optional[Dict[str, Any]]:
    """Get current license information"""
    return _license_info


async def get_all_features() -> Dict[str, bool]:
    """Get all feature entitlements"""
    global _license_info

    if not _license_info:
        return {}

    features = {}
    for feature in _license_info.get("features", []):
        features[feature.get("name")] = feature.get("entitled", False)

    return features


async def send_keepalive(usage_data: Dict[str, Any] = None) -> bool:
    """
    Send keepalive to license server with usage data

    Args:
        usage_data: Optional usage statistics

    Returns:
        True if successful
    """
    config = get_config()

    if not config.LICENSE_KEY:
        return False

    try:
        import socket

        payload = {
            "product": config.PRODUCT_NAME,
            "server_id": f"killkrill-{socket.gethostname()}",
            "hostname": socket.gethostname(),
            "version": "2.0.0",
        }

        if usage_data:
            payload["usage_stats"] = usage_data

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.LICENSE_SERVER_URL}/api/v2/keepalive",
                headers={"Authorization": f"Bearer {config.LICENSE_KEY}"},
                json=payload,
                timeout=10.0,
            )

            return response.status_code == 200

    except Exception as e:
        logger.error("keepalive_failed", error=str(e))
        return False


def is_license_valid() -> bool:
    """Check if license is currently valid"""
    return _license_valid
