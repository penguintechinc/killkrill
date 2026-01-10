"""
KillKrill Authentication Module
Provides authentication and authorization utilities for both py4web and Quart frameworks
"""

from shared.auth.middleware import (
    AuthenticationError,
    AuthorizationError,
    MultiAuthMiddleware,
    generate_api_key,
    generate_jwt_token,
    hash_api_key,
)
from shared.auth.middleware import require_auth as require_auth_py4web
from shared.auth.middleware import require_ip_access as require_ip_access_py4web
from shared.auth.middleware import (
    verify_api_key,
)
from shared.auth.middleware import verify_auth as verify_auth_py4web
from shared.auth.middleware import (
    verify_ip_access,
    verify_jwt_token,
)

# Conditionally import Quart-specific auth (only if Quart is installed)
try:
    from shared.auth.quart_auth import (
        require_auth,
        require_ip_access,
        require_permission,
        require_role,
        verify_auth,
    )
except ImportError:
    # Quart not installed, skip Quart-specific decorators
    require_auth = None
    require_permission = None
    require_role = None
    verify_auth = None

__all__ = [
    # Exceptions
    "AuthenticationError",
    "AuthorizationError",
    # Utilities
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    "generate_jwt_token",
    "verify_jwt_token",
    "verify_ip_access",
    # Middleware
    "MultiAuthMiddleware",
    # py4web decorators
    "require_auth_py4web",
    "require_ip_access_py4web",
    "verify_auth_py4web",
    # Quart decorators
    "require_auth",
    "require_role",
    "require_permission",
    "require_ip_access",
    "verify_auth",
]
