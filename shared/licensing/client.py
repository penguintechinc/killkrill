"""
PenguinTech License Server Client
Universal licensing integration for KillKrill observability platform
"""

import requests
import time
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class PenguinTechLicenseClient:
    """Client for PenguinTech License Server integration"""

    def __init__(self, license_key: str, product: str, base_url: str = "https://license.penguintech.io"):
        self.license_key = license_key
        self.product = product
        self.base_url = base_url
        self.server_id: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {license_key}",
            "Content-Type": "application/json"
        })
        self._cache: Dict[str, Any] = {}
        self._cache_timeout = 300  # 5 minutes

    def validate(self) -> Dict[str, Any]:
        """Validate license and get server ID for keepalives"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/validate",
                json={"product": self.product},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    self.server_id = data.get("metadata", {}).get("server_id")
                    self._cache['validation'] = {
                        'data': data,
                        'timestamp': time.time()
                    }
                    return data

            return {
                "valid": False,
                "message": f"Validation failed: {response.status_code} - {response.text}"
            }

        except Exception as e:
            logger.error(f"License validation error: {e}")
            return {
                "valid": False,
                "message": f"Validation error: {str(e)}"
            }

    def check_feature(self, feature: str, use_cache: bool = True) -> bool:
        """Check if specific feature is enabled"""
        cache_key = f"feature_{feature}"

        # Check cache first
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached['timestamp'] < self._cache_timeout:
                return cached['data']

        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/features",
                json={"product": self.product, "feature": feature},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                features = data.get("features", [])
                enabled = features[0].get("entitled", False) if features else False

                # Cache result
                self._cache[cache_key] = {
                    'data': enabled,
                    'timestamp': time.time()
                }

                return enabled

            return False

        except Exception as e:
            logger.warning(f"Feature check error for {feature}: {e}")
            return False

    def get_limits(self) -> Dict[str, int]:
        """Get license limits"""
        validation_data = self._get_cached_validation()
        if validation_data and validation_data.get("valid"):
            return validation_data.get("limits", {})
        return {}

    def get_tier(self) -> str:
        """Get license tier"""
        validation_data = self._get_cached_validation()
        if validation_data and validation_data.get("valid"):
            return validation_data.get("tier", "community")
        return "community"

    def keepalive(self, usage_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send keepalive with optional usage statistics"""
        if not self.server_id:
            validation = self.validate()
            if not validation.get("valid"):
                return validation

        payload = {
            "product": self.product,
            "server_id": self.server_id,
            "hostname": "killkrill-cluster",
            "version": "1.0.0",
            "uptime_seconds": int(time.time())
        }

        if usage_data:
            payload.update(usage_data)

        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/keepalive",
                json=payload,
                timeout=15
            )

            return response.json()

        except Exception as e:
            logger.error(f"Keepalive error: {e}")
            return {"error": str(e)}

    def _get_cached_validation(self) -> Optional[Dict[str, Any]]:
        """Get cached validation data if not expired"""
        if 'validation' in self._cache:
            cached = self._cache['validation']
            if time.time() - cached['timestamp'] < self._cache_timeout:
                return cached['data']
        return None


def requires_feature(feature_name: str):
    """Decorator to gate functionality behind license features"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # This would be set globally in the app
            client = getattr(wrapper, '_license_client', None)
            if not client:
                raise Exception("License client not configured")

            if not client.check_feature(feature_name):
                raise FeatureNotAvailableError(
                    f"Feature '{feature_name}' requires license upgrade"
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


class FeatureNotAvailableError(Exception):
    """Exception raised when a feature is not available in current license tier"""
    pass


# License tiers and their features
LICENSE_FEATURES = {
    "community": [
        "basic_log_ingestion",
        "basic_metrics",
        "single_source"
    ],
    "professional": [
        "basic_log_ingestion",
        "basic_metrics",
        "single_source",
        "multiple_sources",
        "advanced_filtering",
        "retention_30_days",
        "api_access"
    ],
    "enterprise": [
        "basic_log_ingestion",
        "basic_metrics",
        "single_source",
        "multiple_sources",
        "advanced_filtering",
        "retention_30_days",
        "api_access",
        "retention_1_year",
        "sso_integration",
        "audit_logging",
        "ha_deployment",
        "priority_support"
    ]
}


def get_tier_features(tier: str) -> List[str]:
    """Get list of features available for a license tier"""
    return LICENSE_FEATURES.get(tier.lower(), LICENSE_FEATURES["community"])