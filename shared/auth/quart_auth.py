"""
Quart-compatible authentication decorators
Port of py4web auth middleware for Quart async framework
"""

import jwt
import hashlib
import secrets
import time
import logging
from typing import Optional, Dict, Any, Callable, List
from functools import wraps
from netaddr import IPNetwork, AddrFormatError

from quart import request, g, abort, jsonify

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


def generate_jwt_token(payload: Dict[str, Any], secret: str, expiry_hours: int = 24) -> str:
    """Generate a JWT token"""
    exp_time = int(time.time()) + (expiry_hours * 3600)
    payload.update({
        'exp': exp_time,
        'iat': int(time.time())
    })
    return jwt.encode(payload, secret, algorithm='HS256')


def verify_jwt_token(token: str, secret: str) -> Dict[str, Any]:
    """Verify and decode a JWT token"""
    try:
        return jwt.decode(token, secret, algorithms=['HS256'])
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid JWT token: {str(e)}")


def verify_ip_access(client_ip: str, allowed_networks: List[str]) -> bool:
    """Verify client IP against allowed networks (supports CIDR)"""
    if not allowed_networks:
        return True

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
    """Multi-method authentication middleware for Quart"""

    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret

    def authenticate_request(self, headers: Dict[str, str], query_params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Authenticate request using multiple methods:
        1. API Key (X-API-Key header or api_key query param)
        2. JWT Token (Authorization: Bearer header)
        3. mTLS (X-Client-Cert header with certificate)
        """

        # Method 1: API Key authentication
        api_key = headers.get('x-api-key') or query_params.get('api_key')
        if api_key:
            auth_result = self._authenticate_api_key(api_key)
            if auth_result:
                return auth_result

        # Method 2: JWT Token authentication
        auth_header = headers.get('authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            auth_result = self._authenticate_jwt(token)
            if auth_result:
                return auth_result

        # Method 3: mTLS authentication
        client_cert = headers.get('x-client-cert')
        if client_cert:
            auth_result = self._authenticate_mtls(client_cert)
            if auth_result:
                return auth_result

        return None

    def _authenticate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Authenticate via API key (to be implemented with database lookup)"""
        return {
            'method': 'api_key',
            'authenticated': True,
            'user_id': 'api_user',
            'permissions': ['read', 'write']
        }

    def _authenticate_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Authenticate via JWT token"""
        try:
            payload = verify_jwt_token(token, self.jwt_secret)
            return {
                'method': 'jwt',
                'authenticated': True,
                'user_id': payload.get('user_id'),
                'permissions': payload.get('permissions', []),
                'source': payload.get('source'),
                'expires': payload.get('exp')
            }
        except AuthenticationError:
            return None

    def _authenticate_mtls(self, client_cert: str) -> Optional[Dict[str, Any]]:
        """Authenticate via mTLS certificate"""
        return {
            'method': 'mtls',
            'authenticated': True,
            'client_cert_fingerprint': hashlib.sha256(client_cert.encode()).hexdigest()[:16],
            'permissions': ['read', 'write']
        }


def require_auth(jwt_secret: Optional[str] = None) -> Callable:
    """
    Decorator to require authentication on a Quart route

    Usage:
        @bp.route('/protected')
        @require_auth()
        async def protected_endpoint():
            auth_result = g.auth_result
            return {'message': 'Protected resource'}

    Args:
        jwt_secret: JWT secret key for token verification (required)

    Returns:
        Decorator function for async route handlers

    Raises:
        401 Unauthorized if authentication fails
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not jwt_secret:
                logger.error("JWT secret not provided to require_auth decorator")
                return await abort(500)

            headers = {k.lower(): v for k, v in request.headers.items()}
            query_params = dict(await request.args)

            auth_middleware = MultiAuthMiddleware(jwt_secret)
            auth_result = auth_middleware.authenticate_request(headers, query_params)

            if not auth_result or not auth_result.get('authenticated'):
                return await abort(401)

            g.auth_result = auth_result
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_role(required_role: str) -> Callable:
    """
    Decorator to require specific role for Quart route
    Must be used with require_auth decorator

    Usage:
        @bp.route('/admin')
        @require_auth()
        @require_role('admin')
        async def admin_endpoint():
            return {'message': 'Admin resource'}

    Args:
        required_role: Role name required for access

    Returns:
        Decorator function for async route handlers

    Raises:
        403 Forbidden if user lacks required role
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not hasattr(g, 'auth_result') or not g.auth_result:
                return await abort(401)

            user_role = g.auth_result.get('role')
            if user_role != required_role:
                return await abort(403)

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_permission(required_permission: str) -> Callable:
    """
    Decorator to require specific permission for Quart route
    Must be used with require_auth decorator

    Usage:
        @bp.route('/write')
        @require_auth()
        @require_permission('write')
        async def write_endpoint():
            return {'message': 'Write resource'}

    Args:
        required_permission: Permission name required for access

    Returns:
        Decorator function for async route handlers

    Raises:
        403 Forbidden if user lacks required permission
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not hasattr(g, 'auth_result') or not g.auth_result:
                return await abort(401)

            user_permissions = g.auth_result.get('permissions', [])
            if required_permission not in user_permissions:
                return await abort(403)

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_ip_access(allowed_networks: List[str]) -> Callable:
    """
    Decorator to restrict access by IP address
    Supports CIDR notation for network ranges

    Usage:
        @bp.route('/internal')
        @require_ip_access(['192.168.1.0/24', '10.0.0.0/8'])
        async def internal_endpoint():
            return {'message': 'Internal resource'}

    Args:
        allowed_networks: List of CIDR networks or IP addresses

    Returns:
        Decorator function for async route handlers

    Raises:
        403 Forbidden if client IP is not in allowed networks
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            client_ip = request.remote_addr or '127.0.0.1'
            if not verify_ip_access(client_ip, allowed_networks):
                return await abort(403)

            return await func(*args, **kwargs)

        return wrapper
    return decorator


async def verify_auth(
    jwt_secret: str,
    allowed_networks: Optional[List[str]] = None
) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Standalone authentication verification for Quart requests

    Usage:
        authenticated, auth_context = await verify_auth(
            jwt_secret=app.config['JWT_SECRET']
        )

    Args:
        jwt_secret: JWT secret for token verification
        allowed_networks: Optional list of allowed CIDR networks

    Returns:
        Tuple of (authenticated: bool, auth_context: dict or None)
    """
    try:
        client_ip = request.remote_addr or '127.0.0.1'

        if allowed_networks and not verify_ip_access(client_ip, allowed_networks):
            return False, None

        headers = {k.lower(): v for k, v in request.headers.items()}
        query_params = dict(await request.args)

        auth_middleware = MultiAuthMiddleware(jwt_secret)
        auth_result = auth_middleware.authenticate_request(headers, query_params)

        if auth_result and auth_result.get('authenticated'):
            return True, auth_result

        return False, None

    except Exception as e:
        logger.error(f"Authentication verification error: {e}")
        return False, None
