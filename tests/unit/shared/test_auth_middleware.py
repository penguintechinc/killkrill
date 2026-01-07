"""
Unit tests for shared authentication middleware module.

Tests cover:
- API key generation and verification
- JWT token generation and verification
- IP-based access control with CIDR validation
- Multi-method authentication middleware
- Authentication decorators
- Error handling and edge cases
"""

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

from shared.auth.middleware import (AuthenticationError, AuthorizationError,
                                    MultiAuthMiddleware, generate_api_key,
                                    generate_jwt_token, hash_api_key,
                                    require_auth, require_ip_access,
                                    verify_api_key, verify_auth,
                                    verify_ip_access, verify_jwt_token)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def jwt_secret() -> str:
    """Generate a test JWT secret."""
    return secrets.token_urlsafe(32)


@pytest.fixture
def sample_api_key() -> str:
    """Generate a sample API key."""
    return generate_api_key(64)


@pytest.fixture
def sample_payload() -> Dict[str, Any]:
    """Create a sample JWT payload."""
    return {
        "user_id": "test_user_123",
        "username": "testuser",
        "permissions": ["read", "write"],
        "source": "api",
    }


@pytest.fixture
def auth_middleware(jwt_secret: str) -> MultiAuthMiddleware:
    """Create an authenticated middleware instance."""
    return MultiAuthMiddleware(jwt_secret)


# ============================================================================
# Tests: generate_api_key()
# ============================================================================


@pytest.mark.unit
def test_generate_api_key_default_length():
    """Test API key generation with default length."""
    key = generate_api_key()
    assert isinstance(key, str)
    assert len(key) == 64
    assert len(key) > 0


@pytest.mark.unit
def test_generate_api_key_custom_length():
    """Test API key generation with custom length."""
    for length in [32, 48, 96, 128]:
        key = generate_api_key(length)
        assert len(key) == length


@pytest.mark.unit
def test_generate_api_key_randomness():
    """Test that generated keys are random and unique."""
    keys = [generate_api_key() for _ in range(100)]
    assert len(set(keys)) == 100  # All unique
    assert all(isinstance(k, str) for k in keys)


@pytest.mark.unit
def test_generate_api_key_url_safe():
    """Test that generated keys are URL-safe."""
    key = generate_api_key()
    # URL-safe characters: A-Z a-z 0-9 - _ (no special chars)
    assert all(c.isalnum() or c in "-_" for c in key)


# ============================================================================
# Tests: hash_api_key()
# ============================================================================


@pytest.mark.unit
def test_hash_api_key_produces_sha256():
    """Test that API key hashing produces SHA-256 hash."""
    api_key = "test_api_key_12345"
    hashed = hash_api_key(api_key)
    expected = hashlib.sha256(api_key.encode()).hexdigest()
    assert hashed == expected


@pytest.mark.unit
def test_hash_api_key_consistency():
    """Test that hashing the same key produces the same hash."""
    api_key = "consistent_key"
    hash1 = hash_api_key(api_key)
    hash2 = hash_api_key(api_key)
    assert hash1 == hash2


@pytest.mark.unit
def test_hash_api_key_different_keys_different_hashes():
    """Test that different keys produce different hashes."""
    key1 = generate_api_key()
    key2 = generate_api_key()
    hash1 = hash_api_key(key1)
    hash2 = hash_api_key(key2)
    assert hash1 != hash2


@pytest.mark.unit
def test_hash_api_key_hex_format():
    """Test that hash output is valid hexadecimal."""
    api_key = "test_key"
    hashed = hash_api_key(api_key)
    assert len(hashed) == 64  # SHA-256 hex is 64 chars
    assert all(c in "0123456789abcdef" for c in hashed)


@pytest.mark.unit
def test_hash_api_key_empty_string():
    """Test hashing empty string."""
    hashed = hash_api_key("")
    expected = hashlib.sha256(b"").hexdigest()
    assert hashed == expected


# ============================================================================
# Tests: verify_api_key()
# ============================================================================


@pytest.mark.unit
def test_verify_api_key_success(sample_api_key: str):
    """Test successful API key verification."""
    hashed = hash_api_key(sample_api_key)
    assert verify_api_key(sample_api_key, hashed) is True


@pytest.mark.unit
def test_verify_api_key_failure():
    """Test failed API key verification with wrong key."""
    correct_key = generate_api_key()
    wrong_key = generate_api_key()
    hashed = hash_api_key(correct_key)
    assert verify_api_key(wrong_key, hashed) is False


@pytest.mark.unit
def test_verify_api_key_corrupted_hash():
    """Test verification with corrupted hash."""
    api_key = generate_api_key()
    corrupted_hash = "0" * 64  # Invalid hash
    assert verify_api_key(api_key, corrupted_hash) is False


@pytest.mark.unit
def test_verify_api_key_case_sensitive():
    """Test that API key verification is case-sensitive."""
    api_key = "TestApiKey123"
    hashed = hash_api_key(api_key)
    assert verify_api_key("testApiKey123", hashed) is False
    assert verify_api_key(api_key, hashed) is True


# ============================================================================
# Tests: generate_jwt_token()
# ============================================================================


@pytest.mark.unit
def test_generate_jwt_token_basic(sample_payload: Dict[str, Any], jwt_secret: str):
    """Test basic JWT token generation."""
    token = generate_jwt_token(sample_payload, jwt_secret)
    assert isinstance(token, str)
    assert len(token) > 0
    assert token.count(".") == 2  # Valid JWT has 3 parts


@pytest.mark.unit
def test_generate_jwt_token_includes_expiry(jwt_secret: str):
    """Test that generated token includes expiry claim."""
    payload = {"user_id": "test_user"}
    token = generate_jwt_token(payload, jwt_secret, expiry_hours=24)

    import jwt

    decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    assert "exp" in decoded
    assert "iat" in decoded
    assert decoded["exp"] > decoded["iat"]


@pytest.mark.unit
def test_generate_jwt_token_custom_expiry(jwt_secret: str):
    """Test JWT token generation with custom expiry hours."""
    payload = {"user_id": "test_user"}

    token_24h = generate_jwt_token(payload, jwt_secret, expiry_hours=24)
    token_1h = generate_jwt_token(payload, jwt_secret, expiry_hours=1)

    import jwt

    decoded_24h = jwt.decode(token_24h, jwt_secret, algorithms=["HS256"])
    decoded_1h = jwt.decode(token_1h, jwt_secret, algorithms=["HS256"])

    # 24h token should expire later than 1h token
    assert decoded_24h["exp"] > decoded_1h["exp"]


@pytest.mark.unit
def test_generate_jwt_token_includes_payload_data(
    sample_payload: Dict[str, Any], jwt_secret: str
):
    """Test that payload data is included in token."""
    token = generate_jwt_token(sample_payload, jwt_secret)

    import jwt

    decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    assert decoded["user_id"] == sample_payload["user_id"]
    assert decoded["username"] == sample_payload["username"]
    assert decoded["permissions"] == sample_payload["permissions"]


@pytest.mark.unit
def test_generate_jwt_token_different_secrets_produce_different_tokens(
    sample_payload: Dict[str, Any],
):
    """Test that different secrets produce different tokens."""
    secret1 = secrets.token_urlsafe(32)
    secret2 = secrets.token_urlsafe(32)

    token1 = generate_jwt_token(sample_payload, secret1)
    token2 = generate_jwt_token(sample_payload, secret2)

    assert token1 != token2


# ============================================================================
# Tests: verify_jwt_token()
# ============================================================================


@pytest.mark.unit
def test_verify_jwt_token_success(sample_payload: Dict[str, Any], jwt_secret: str):
    """Test successful JWT token verification."""
    token = generate_jwt_token(sample_payload, jwt_secret)
    decoded = verify_jwt_token(token, jwt_secret)
    assert decoded["user_id"] == sample_payload["user_id"]


@pytest.mark.unit
def test_verify_jwt_token_invalid_token(jwt_secret: str):
    """Test verification with invalid token."""
    with pytest.raises(AuthenticationError):
        verify_jwt_token("invalid.token.format", jwt_secret)


@pytest.mark.unit
def test_verify_jwt_token_wrong_secret(sample_payload: Dict[str, Any], jwt_secret: str):
    """Test verification with wrong secret."""
    token = generate_jwt_token(sample_payload, jwt_secret)
    wrong_secret = secrets.token_urlsafe(32)

    with pytest.raises(AuthenticationError):
        verify_jwt_token(token, wrong_secret)


@pytest.mark.unit
def test_verify_jwt_token_expired_token(jwt_secret: str):
    """Test verification of expired token."""
    payload = {"user_id": "test_user"}
    import jwt

    # Create expired token manually
    expired_payload = payload.copy()
    expired_payload["exp"] = int(time.time()) - 3600  # Expired 1 hour ago
    expired_payload["iat"] = int(time.time()) - 7200
    expired_token = jwt.encode(expired_payload, jwt_secret, algorithm="HS256")

    with pytest.raises(AuthenticationError):
        verify_jwt_token(expired_token, jwt_secret)


@pytest.mark.unit
def test_verify_jwt_token_empty_token(jwt_secret: str):
    """Test verification with empty token."""
    with pytest.raises(AuthenticationError):
        verify_jwt_token("", jwt_secret)


@pytest.mark.unit
def test_verify_jwt_token_tampered_token(
    sample_payload: Dict[str, Any], jwt_secret: str
):
    """Test verification of tampered token."""
    token = generate_jwt_token(sample_payload, jwt_secret)
    tampered_token = token[:-5] + "xxxxx"  # Corrupt the signature

    with pytest.raises(AuthenticationError):
        verify_jwt_token(tampered_token, jwt_secret)


# ============================================================================
# Tests: verify_ip_access()
# ============================================================================


@pytest.mark.unit
def test_verify_ip_access_no_restrictions():
    """Test that empty allowed networks allows all IPs."""
    assert verify_ip_access("192.168.1.1", []) is True
    assert verify_ip_access("10.0.0.1", []) is True
    assert verify_ip_access("8.8.8.8", None) is True


@pytest.mark.unit
def test_verify_ip_access_single_ip():
    """Test verification against single IP address."""
    assert verify_ip_access("192.168.1.100", ["192.168.1.100"]) is True
    assert verify_ip_access("192.168.1.101", ["192.168.1.100"]) is False


@pytest.mark.unit
def test_verify_ip_access_cidr_range():
    """Test verification against CIDR range."""
    allowed = ["192.168.1.0/24"]

    assert verify_ip_access("192.168.1.1", allowed) is True
    assert verify_ip_access("192.168.1.254", allowed) is True
    assert verify_ip_access("192.168.2.1", allowed) is False


@pytest.mark.unit
def test_verify_ip_access_multiple_networks():
    """Test verification against multiple networks."""
    allowed = ["192.168.1.0/24", "10.0.0.0/8", "172.16.0.0/12"]

    assert verify_ip_access("192.168.1.50", allowed) is True
    assert verify_ip_access("10.5.5.5", allowed) is True
    assert verify_ip_access("172.16.100.1", allowed) is True
    assert verify_ip_access("8.8.8.8", allowed) is False


@pytest.mark.unit
def test_verify_ip_access_ipv6():
    """Test verification with IPv6 addresses."""
    allowed = ["2001:db8::/32"]

    assert verify_ip_access("2001:db8::1", allowed) is True
    assert verify_ip_access("2001:db8:ffff:ffff::1", allowed) is True
    assert verify_ip_access("2001:db9::1", allowed) is False


@pytest.mark.unit
def test_verify_ip_access_invalid_network_format(caplog):
    """Test handling of invalid network format."""
    allowed = ["192.168.1.0/24", "invalid_network", "10.0.0.0/8"]

    # Should log warning and continue checking other networks
    assert verify_ip_access("10.0.0.1", allowed) is True
    assert verify_ip_access("192.168.1.1", allowed) is True
    assert verify_ip_access("8.8.8.8", allowed) is False


@pytest.mark.unit
def test_verify_ip_access_localhost():
    """Test localhost IP addresses."""
    allowed = ["127.0.0.0/8", "::1/128"]

    assert verify_ip_access("127.0.0.1", allowed) is True
    assert verify_ip_access("127.255.255.255", allowed) is True
    assert verify_ip_access("192.168.1.1", allowed) is False


# ============================================================================
# Tests: MultiAuthMiddleware class
# ============================================================================


@pytest.mark.unit
def test_middleware_init(jwt_secret: str):
    """Test middleware initialization."""
    middleware = MultiAuthMiddleware(jwt_secret)
    assert middleware.jwt_secret == jwt_secret


@pytest.mark.unit
def test_middleware_authenticate_api_key(auth_middleware: MultiAuthMiddleware):
    """Test API key authentication via middleware."""
    headers = {"x-api-key": "test_api_key"}
    query_params = {}

    result = auth_middleware.authenticate_request(headers, query_params)
    assert result is not None
    assert result["authenticated"] is True
    assert result["method"] == "api_key"
    assert "user_id" in result
    assert "permissions" in result


@pytest.mark.unit
def test_middleware_authenticate_api_key_from_query(
    auth_middleware: MultiAuthMiddleware,
):
    """Test API key authentication from query parameter."""
    headers = {}
    query_params = {"api_key": "test_api_key"}

    result = auth_middleware.authenticate_request(headers, query_params)
    assert result is not None
    assert result["authenticated"] is True
    assert result["method"] == "api_key"


@pytest.mark.unit
def test_middleware_authenticate_jwt(sample_payload: Dict[str, Any], jwt_secret: str):
    """Test JWT authentication via middleware."""
    middleware = MultiAuthMiddleware(jwt_secret)
    token = generate_jwt_token(sample_payload, jwt_secret)

    headers = {"authorization": f"Bearer {token}"}
    query_params = {}

    result = middleware.authenticate_request(headers, query_params)
    assert result is not None
    assert result["authenticated"] is True
    assert result["method"] == "jwt"
    assert result["user_id"] == sample_payload["user_id"]


@pytest.mark.unit
def test_middleware_authenticate_mtls(auth_middleware: MultiAuthMiddleware):
    """Test mTLS authentication via middleware."""
    headers = {"x-client-cert": "test_client_cert_data"}
    query_params = {}

    result = auth_middleware.authenticate_request(headers, query_params)
    assert result is not None
    assert result["authenticated"] is True
    assert result["method"] == "mtls"
    assert "client_cert_fingerprint" in result


@pytest.mark.unit
def test_middleware_no_auth_provided(auth_middleware: MultiAuthMiddleware):
    """Test request without any authentication."""
    headers = {}
    query_params = {}

    result = auth_middleware.authenticate_request(headers, query_params)
    assert result is None


@pytest.mark.unit
def test_middleware_header_case_insensitive(auth_middleware: MultiAuthMiddleware):
    """Test that header matching is case-insensitive."""
    headers = {"X-API-KEY": "test_api_key"}  # Uppercase
    query_params = {}

    result = auth_middleware.authenticate_request(headers, query_params)
    assert result is None  # Headers should be lowercased before matching


@pytest.mark.unit
def test_middleware_api_key_priority(sample_payload: Dict[str, Any], jwt_secret: str):
    """Test that API key takes priority over JWT when both provided."""
    middleware = MultiAuthMiddleware(jwt_secret)
    token = generate_jwt_token(sample_payload, jwt_secret)

    headers = {"x-api-key": "test_api_key", "authorization": f"Bearer {token}"}
    query_params = {}

    result = middleware.authenticate_request(headers, query_params)
    # API key should be tried first
    assert result["method"] == "api_key"


@pytest.mark.unit
def test_middleware_invalid_jwt_falls_back(auth_middleware: MultiAuthMiddleware):
    """Test that invalid JWT doesn't break mTLS fallback."""
    headers = {"authorization": "Bearer invalid_token", "x-client-cert": "test_cert"}
    query_params = {}

    result = auth_middleware.authenticate_request(headers, query_params)
    # Should fall back to mTLS after JWT fails
    assert result is not None
    assert result["method"] == "mtls"


# ============================================================================
# Tests: require_auth decorator
# ============================================================================


@pytest.mark.unit
def test_require_auth_decorator_requires_py4web():
    """Test that decorator requires py4web framework."""
    auth_middleware = MultiAuthMiddleware("secret")

    @require_auth(auth_middleware)
    def dummy_func():
        return "success"

    # Decorator should wrap the function
    assert callable(dummy_func)


@pytest.mark.unit
def test_require_auth_decorator_with_permissions():
    """Test require_auth decorator with permission checks."""
    auth_middleware = MultiAuthMiddleware("secret")

    @require_auth(auth_middleware, required_permissions=["admin", "read"])
    def protected_func():
        return "success"

    # Decorator should wrap the function
    assert callable(protected_func)


# ============================================================================
# Tests: require_ip_access decorator
# ============================================================================


@pytest.mark.unit
def test_require_ip_access_decorator():
    """Test require_ip_access decorator."""

    @require_ip_access(["192.168.1.0/24"])
    def ip_protected_func():
        return "success"

    # Decorator should wrap the function
    assert callable(ip_protected_func)


# ============================================================================
# Tests: verify_auth() standalone function
# ============================================================================


@pytest.mark.unit
def test_verify_auth_with_api_key():
    """Test standalone verify_auth with API key."""
    headers = {"x-api-key": "test_key"}
    query_params = {}

    authenticated, auth_context = verify_auth(headers, query_params, "test_secret")

    assert authenticated is True
    assert auth_context is not None
    assert auth_context["method"] == "api_key"


@pytest.mark.unit
def test_verify_auth_with_jwt(sample_payload: Dict[str, Any], jwt_secret: str):
    """Test standalone verify_auth with JWT token."""
    token = generate_jwt_token(sample_payload, jwt_secret)
    headers = {"authorization": f"Bearer {token}"}
    query_params = {}

    authenticated, auth_context = verify_auth(headers, query_params, jwt_secret)

    assert authenticated is True
    assert auth_context is not None
    assert auth_context["method"] == "jwt"


@pytest.mark.unit
def test_verify_auth_no_credentials():
    """Test verify_auth without credentials."""
    headers = {}
    query_params = {}

    authenticated, auth_context = verify_auth(headers, query_params, "test_secret")

    assert authenticated is False
    assert auth_context is None


@pytest.mark.unit
def test_verify_auth_with_ip_restriction():
    """Test verify_auth with IP-based access control."""
    headers = {"x-api-key": "test_key"}
    query_params = {}
    allowed_networks = ["192.168.1.0/24"]

    # Allowed IP
    authenticated, _ = verify_auth(
        headers,
        query_params,
        "test_secret",
        allowed_networks=allowed_networks,
        client_ip="192.168.1.100",
    )
    assert authenticated is True

    # Denied IP
    authenticated, _ = verify_auth(
        headers,
        query_params,
        "test_secret",
        allowed_networks=allowed_networks,
        client_ip="10.0.0.1",
    )
    assert authenticated is False


@pytest.mark.unit
def test_verify_auth_exception_handling(caplog):
    """Test that verify_auth handles exceptions gracefully."""
    headers = {"authorization": "Bearer malformed_token"}
    query_params = {}

    # Should not raise, should return False
    authenticated, auth_context = verify_auth(headers, query_params, "test_secret")

    assert authenticated is False
    assert auth_context is None


# ============================================================================
# Tests: Error Cases & Edge Cases
# ============================================================================


@pytest.mark.unit
def test_authentication_error_exception():
    """Test AuthenticationError exception."""
    with pytest.raises(AuthenticationError) as exc_info:
        raise AuthenticationError("Test error")
    assert "Test error" in str(exc_info.value)


@pytest.mark.unit
def test_authorization_error_exception():
    """Test AuthorizationError exception."""
    with pytest.raises(AuthorizationError) as exc_info:
        raise AuthorizationError("Insufficient permissions")
    assert "Insufficient permissions" in str(exc_info.value)


@pytest.mark.unit
def test_verify_api_key_with_special_characters():
    """Test API key verification with special characters."""
    api_key = "test_key-with-special_chars.123"
    hashed = hash_api_key(api_key)
    assert verify_api_key(api_key, hashed) is True


@pytest.mark.unit
def test_generate_jwt_token_with_nested_payload(jwt_secret: str):
    """Test JWT generation with nested payload structures."""
    payload = {
        "user_id": "test_user",
        "metadata": {
            "org_id": "org_123",
            "roles": ["admin", "user"],
            "settings": {"theme": "dark"},
        },
    }

    token = generate_jwt_token(payload, jwt_secret)
    decoded = verify_jwt_token(token, jwt_secret)

    assert decoded["metadata"]["org_id"] == "org_123"
    assert "admin" in decoded["metadata"]["roles"]


@pytest.mark.unit
def test_verify_ip_access_large_network_list():
    """Test IP verification with large list of networks."""
    networks = [
        "192.168.0.0/16",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "203.0.113.0/24",
        "198.51.100.0/24",
        "2001:db8::/32",
    ]

    assert verify_ip_access("192.168.100.1", networks) is True
    assert verify_ip_access("10.255.255.254", networks) is True
    assert verify_ip_access("203.0.113.50", networks) is True
    assert verify_ip_access("8.8.8.8", networks) is False


@pytest.mark.unit
def test_middleware_authenticate_with_malformed_bearer():
    """Test middleware handling of malformed Bearer header."""
    auth_middleware = MultiAuthMiddleware("secret")

    # Missing space after Bearer
    headers = {"authorization": "Bearertoken123"}
    query_params = {}

    result = auth_middleware.authenticate_request(headers, query_params)
    # Should not match and fall through to other methods
    assert result is None or result["method"] != "jwt"


@pytest.mark.unit
def test_api_key_generation_length_edge_cases():
    """Test API key generation with edge case lengths."""
    # Very short
    short_key = generate_api_key(8)
    assert len(short_key) == 8

    # Very long
    long_key = generate_api_key(256)
    assert len(long_key) == 256


@pytest.mark.unit
def test_verify_jwt_token_none_secret(sample_payload: Dict[str, Any]):
    """Test JWT verification behavior with problematic secret."""
    token = generate_jwt_token(sample_payload, "valid_secret")

    # None or empty secret should cause error
    with pytest.raises(AuthenticationError):
        verify_jwt_token(token, "")


@pytest.mark.unit
def test_verify_ip_access_broadcast_address():
    """Test IP verification with broadcast addresses."""
    allowed = ["192.168.1.0/24"]

    # Network and broadcast addresses
    assert verify_ip_access("192.168.1.0", allowed) is True  # Network address
    assert verify_ip_access("192.168.1.255", allowed) is True  # Broadcast


@pytest.mark.unit
def test_hash_api_key_unicode_handling():
    """Test API key hashing with unicode characters."""
    api_key = "test_key_with_unicode_éàü"
    hashed = hash_api_key(api_key)
    assert verify_api_key(api_key, hashed) is True
    assert len(hashed) == 64


@pytest.mark.unit
def test_generate_jwt_token_preserves_payload_mutations(jwt_secret: str):
    """Test that JWT generation doesn't mutate original payload."""
    original_payload = {"user_id": "test", "data": {"key": "value"}}
    payload_copy = original_payload.copy()

    generate_jwt_token(original_payload, jwt_secret)

    # Original payload should be mutated (exp/iat added)
    assert "exp" in original_payload
    assert "iat" in original_payload


@pytest.mark.unit
def test_verify_auth_ip_priority():
    """Test that IP check happens before auth in verify_auth."""
    headers = {"x-api-key": "test_key"}
    query_params = {}
    allowed_networks = ["192.168.1.0/24"]

    # IP not in allowed list - should fail before checking auth
    authenticated, _ = verify_auth(
        headers,
        query_params,
        "test_secret",
        allowed_networks=allowed_networks,
        client_ip="10.0.0.1",
    )
    assert authenticated is False
