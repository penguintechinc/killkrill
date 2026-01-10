"""
KillKrill API - Authentication Middleware
Multi-method authentication: JWT, API Key, License Key
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import jwt
import structlog
from passlib.hash import bcrypt
from quart import g, jsonify, request

from config import get_config

logger = structlog.get_logger(__name__)


class AuthMiddleware:
    """
    Multi-method authentication middleware for Quart
    Supports: JWT Bearer tokens, API Keys, License Keys
    """

    # Endpoints that don't require authentication
    PUBLIC_ENDPOINTS = [
        "/healthz",
        "/metrics",
        "/",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/sensors/results",  # Sensors submit results with API key
    ]

    @staticmethod
    async def authenticate() -> None:
        """Before request authentication hook"""
        # Skip auth for public endpoints
        if request.path in AuthMiddleware.PUBLIC_ENDPOINTS:
            g.authenticated = False
            g.auth = None
            return

        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            g.authenticated = False
            g.auth = None
            return

        auth_result = None
        config = get_config()

        # Try API Key authentication first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            auth_result = await AuthMiddleware._authenticate_api_key(api_key)

        # Try JWT Bearer token
        if not auth_result:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                # Check if it's a license key (PENG- prefix)
                if token.startswith("PENG-"):
                    auth_result = await AuthMiddleware._authenticate_license(token)
                else:
                    auth_result = await AuthMiddleware._authenticate_jwt(token)

        # Store auth result
        if auth_result and auth_result.get("authenticated"):
            g.authenticated = True
            g.auth = auth_result
            g.user_id = auth_result.get("user_id")
        else:
            g.authenticated = False
            g.auth = None
            g.user_id = None

    @staticmethod
    async def _authenticate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
        """Authenticate via API key"""
        from models.database import get_db

        try:
            db = await get_db()
            if not db:
                return None

            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            api_key_record = (
                db((db.api_keys.key_hash == key_hash) & (db.api_keys.is_active == True))
                .select()
                .first()
            )

            if not api_key_record:
                logger.warning("api_key_not_found")
                return None

            # Check expiration
            if (
                api_key_record.expires_at
                and api_key_record.expires_at < datetime.utcnow()
            ):
                logger.warning("api_key_expired", key_name=api_key_record.name)
                return None

            # Update last used
            api_key_record.update_record(last_used=datetime.utcnow())
            db.commit()

            # Parse permissions
            permissions = []
            if api_key_record.permissions:
                import json

                try:
                    permissions = json.loads(api_key_record.permissions)
                except json.JSONDecodeError:
                    permissions = api_key_record.permissions.split(",")

            logger.info("api_key_authenticated", key_name=api_key_record.name)

            return {
                "method": "api_key",
                "authenticated": True,
                "user_id": api_key_record.user_id,
                "api_key_id": api_key_record.id,
                "permissions": permissions,
            }

        except Exception as e:
            logger.error("api_key_auth_error", error=str(e))
            return None

    @staticmethod
    async def _authenticate_jwt(token: str) -> Optional[Dict[str, Any]]:
        """Authenticate via JWT token"""
        config = get_config()

        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])

            logger.debug("jwt_authenticated", user_id=payload.get("user_id"))

            return {
                "method": "jwt",
                "authenticated": True,
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "role": payload.get("role", "user"),
                "permissions": payload.get("permissions", []),
                "exp": payload.get("exp"),
            }

        except jwt.ExpiredSignatureError:
            logger.warning("jwt_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("jwt_invalid", error=str(e))
            return None

    @staticmethod
    async def _authenticate_license(license_key: str) -> Optional[Dict[str, Any]]:
        """Authenticate via PenguinTech license key"""
        config = get_config()

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.LICENSE_SERVER_URL}/api/v2/validate",
                    headers={"Authorization": f"Bearer {license_key}"},
                    json={"product": config.PRODUCT_NAME},
                    timeout=10.0,
                )

                if response.status_code != 200:
                    logger.warning(
                        "license_validation_failed", status=response.status_code
                    )
                    return None

                data = response.json()

                if not data.get("valid", False):
                    logger.warning("license_invalid", message=data.get("message"))
                    return None

                # Extract feature entitlements
                features = {f["name"]: f["entitled"] for f in data.get("features", [])}

                logger.info(
                    "license_authenticated",
                    customer=data.get("customer"),
                    tier=data.get("tier"),
                )

                return {
                    "method": "license",
                    "authenticated": True,
                    "customer": data.get("customer"),
                    "tier": data.get("tier"),
                    "features": features,
                    "limits": data.get("limits", {}),
                    "expires_at": data.get("expires_at"),
                }

        except Exception as e:
            logger.error("license_auth_error", error=str(e))
            return None


def require_auth(permissions: List[str] = None):
    """
    Decorator to require authentication for routes

    Args:
        permissions: Optional list of required permissions
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not g.get("authenticated"):
                return (
                    jsonify({"error": "Authentication required", "status_code": 401}),
                    401,
                )

            if permissions:
                user_permissions = g.auth.get("permissions", [])
                if not any(p in user_permissions for p in permissions):
                    return (
                        jsonify(
                            {
                                "error": "Insufficient permissions",
                                "required": permissions,
                                "status_code": 403,
                            }
                        ),
                        403,
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(roles: List[str]):
    """
    Decorator to require specific role(s)

    Args:
        roles: List of allowed roles
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not g.get("authenticated"):
                return (
                    jsonify({"error": "Authentication required", "status_code": 401}),
                    401,
                )

            user_role = g.auth.get("role", "user")
            if user_role not in roles:
                return (
                    jsonify(
                        {
                            "error": "Access denied",
                            "message": f"Required role: {roles}",
                            "status_code": 403,
                        }
                    ),
                    403,
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_feature(feature_name: str):
    """
    Decorator to require license feature entitlement

    Args:
        feature_name: Name of required feature
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if feature is available via license
            if g.get("auth") and g.auth.get("method") == "license":
                features = g.auth.get("features", {})
                if not features.get(feature_name, False):
                    return (
                        jsonify(
                            {
                                "error": "Feature not available",
                                "feature": feature_name,
                                "message": f'Feature "{feature_name}" requires license upgrade',
                                "status_code": 403,
                            }
                        ),
                        403,
                    )
            else:
                # For non-license auth, check via license service
                from services.license_service import check_feature

                if not await check_feature(feature_name):
                    return (
                        jsonify(
                            {
                                "error": "Feature not available",
                                "feature": feature_name,
                                "message": f'Feature "{feature_name}" requires license upgrade',
                                "status_code": 403,
                            }
                        ),
                        403,
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Utility functions


def generate_api_key(length: int = 64) -> str:
    """Generate a secure random API key"""
    return secrets.token_urlsafe(length)[:length]


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.verify(password, password_hash)


def generate_jwt_token(
    user_id: int,
    username: str,
    role: str = "user",
    permissions: List[str] = None,
    expires_hours: int = None,
) -> str:
    """Generate a JWT access token"""
    config = get_config()
    expires_hours = expires_hours or (config.JWT_ACCESS_TOKEN_EXPIRES // 3600)

    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "permissions": permissions or [],
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expires_hours),
    }

    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def generate_refresh_token() -> str:
    """Generate a secure refresh token"""
    return secrets.token_urlsafe(64)
