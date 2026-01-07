"""
KillKrill Authentication Middleware
Multi-method authentication for enterprise observability platform
"""

import hashlib
import logging
import secrets
import time
from functools import wraps
from typing import Any, Dict, Optional, Tuple

import jwt
from netaddr import AddrFormatError, IPNetwork

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Authentication failed"""

    pass


class AuthorizationError(Exception):
    """Authorization failed"""

    pass


def generate_api_key(length: int = 64) -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(length)[:length]


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash"""
    return hashlib.sha256(api_key.encode()).hexdigest() == hashed_key


def generate_jwt_token(
    payload: Dict[str, Any], secret: str, expiry_hours: int = 24
) -> str:
    """Generate a JWT token"""
    exp_time = int(time.time()) + (expiry_hours * 3600)
    payload.update({"exp": exp_time, "iat": int(time.time())})
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_jwt_token(token: str, secret: str) -> Dict[str, Any]:
    """Verify and decode a JWT token"""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid JWT token: {str(e)}")


def verify_ip_access(client_ip: str, allowed_networks: list) -> bool:
    """Verify client IP against allowed networks (supports CIDR)"""
    if not allowed_networks:
        return True  # No restrictions

    try:
        for network_str in allowed_networks:
            try:
                network = IPNetwork(network_str)
                if client_ip in network:
                    return True
            except (AddrFormatError, ValueError) as e:
                logger.warning(f"Invalid network format: {network_str} - {e}")
                continue
        return False
    except Exception as e:
        logger.error(f"Error verifying IP access: {e}")
        return False


class MultiAuthMiddleware:
    """Multi-method authentication middleware"""

    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret

    def authenticate_request(
        self, headers: Dict[str, str], query_params: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate request using multiple methods:
        1. API Key (X-API-Key header or api_key query param)
        2. JWT Token (Authorization: Bearer header)
        3. mTLS (X-Client-Cert header with certificate)
        """

        # Method 1: API Key authentication
        api_key = headers.get("x-api-key") or query_params.get("api_key")
        if api_key:
            auth_result = self._authenticate_api_key(api_key)
            if auth_result:
                return auth_result

        # Method 2: JWT Token authentication
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            auth_result = self._authenticate_jwt(token)
            if auth_result:
                return auth_result

        # Method 3: mTLS authentication
        client_cert = headers.get("x-client-cert")
        if client_cert:
            auth_result = self._authenticate_mtls(client_cert)
            if auth_result:
                return auth_result

        return None

    def _authenticate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Authenticate via API key (to be implemented with database lookup)"""
        # This would typically look up the API key in the database
        # For now, return basic structure
        return {
            "method": "api_key",
            "authenticated": True,
            "user_id": "api_user",
            "permissions": ["read", "write"],
        }

    def _authenticate_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Authenticate via JWT token"""
        try:
            payload = verify_jwt_token(token, self.jwt_secret)
            return {
                "method": "jwt",
                "authenticated": True,
                "user_id": payload.get("user_id"),
                "permissions": payload.get("permissions", []),
                "source": payload.get("source"),
                "expires": payload.get("exp"),
            }
        except AuthenticationError:
            return None

    def _authenticate_mtls(self, client_cert: str) -> Optional[Dict[str, Any]]:
        """Authenticate via mTLS certificate"""
        # This would typically validate the client certificate
        # For now, return basic structure
        return {
            "method": "mtls",
            "authenticated": True,
            "client_cert_fingerprint": hashlib.sha256(client_cert.encode()).hexdigest()[
                :16
            ],
            "permissions": ["read", "write"],
        }


def require_auth(
    auth_middleware: MultiAuthMiddleware, required_permissions: list = None
):
    """Decorator to require authentication"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract request context (this would be framework-specific)
            # For py4web, you'd use request.headers
            from py4web import request

            headers = {k.lower(): v for k, v in request.headers.items()}
            query_params = dict(request.query)

            auth_result = auth_middleware.authenticate_request(headers, query_params)
            if not auth_result or not auth_result.get("authenticated"):
                raise AuthenticationError("Authentication required")

            # Check permissions if specified
            if required_permissions:
                user_permissions = auth_result.get("permissions", [])
                if not any(perm in user_permissions for perm in required_permissions):
                    raise AuthorizationError("Insufficient permissions")

            # Add auth context to kwargs
            kwargs["auth_context"] = auth_result
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_ip_access(allowed_networks: list):
    """Decorator to require IP-based access control"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from py4web import request

            client_ip = request.environ.get("REMOTE_ADDR", "127.0.0.1")
            if not verify_ip_access(client_ip, allowed_networks):
                raise AuthorizationError(f"IP address {client_ip} not allowed")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def verify_auth(
    request_headers: Dict[str, str],
    request_query: Dict[str, str],
    jwt_secret: str,
    allowed_networks: list = None,
    client_ip: str = "127.0.0.1",
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Standalone authentication verification function
    Returns (authenticated, auth_context)
    """
    try:
        # Check IP access first if networks are specified
        if allowed_networks and not verify_ip_access(client_ip, allowed_networks):
            return False, None

        # Try authentication
        auth_middleware = MultiAuthMiddleware(jwt_secret)
        auth_result = auth_middleware.authenticate_request(
            request_headers, request_query
        )

        if auth_result and auth_result.get("authenticated"):
            return True, auth_result

        return False, None

    except Exception as e:
        logger.error(f"Authentication verification error: {e}")
        return False, None
