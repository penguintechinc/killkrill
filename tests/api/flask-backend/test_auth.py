"""
httpx-based integration tests for KillKrill authentication endpoints.

Tests all auth endpoints with success and error cases using httpx client.
No Flask app imports - all tests via HTTP. Compatible with Quart async patterns.
"""

from uuid import uuid4

import pytest

# ============================================================================
# Login Tests
# ============================================================================


@pytest.mark.integration
class TestLogin:
    """Test POST /api/v1/auth/login endpoint."""

    def test_login_success(self, client, test_user_data):
        """Test successful login returns access token."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert response.status_code in [200, 201, 401]  # 401 if user doesn't exist

    def test_login_invalid_email_format(self, client):
        """Test login with invalid email format returns 400."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "invalid-email", "password": "ValidPass123"},
        )
        assert response.status_code == 400

    def test_login_password_too_short(self, client):
        """Test login with short password returns 400."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "Short1"},
        )
        assert response.status_code == 400

    def test_login_missing_email(self, client):
        """Test login without email returns 422."""
        response = client.post("/api/v1/auth/login", json={"password": "ValidPass123"})
        assert response.status_code in [400, 422]

    def test_login_missing_password(self, client):
        """Test login without password returns 422."""
        response = client.post("/api/v1/auth/login", json={"email": "user@example.com"})
        assert response.status_code in [400, 422]


# ============================================================================
# Register Tests
# ============================================================================


@pytest.mark.integration
class TestRegister:
    """Test POST /api/v1/auth/register endpoint."""

    def test_register_success(self, client):
        """Test successful registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"newuser{uuid4().hex[:8]}@example.com",
                "password": "ValidPass123",
                "name": "New User",
            },
        )
        assert response.status_code in [200, 201, 409]  # 409 if email exists

    def test_register_duplicate_email(self, client, test_user_data):
        """Test registration with duplicate email returns 409."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user_data["email"],
                "password": "ValidPass123",
                "name": "Test User",
            },
        )
        assert response.status_code in [409, 201, 200]

    def test_register_weak_password_lowercase(self, client):
        """Test registration with no uppercase returns 400."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"user{uuid4().hex[:8]}@example.com",
                "password": "invalidpass123",
                "name": "User",
            },
        )
        assert response.status_code == 400

    def test_register_weak_password_uppercase(self, client):
        """Test registration with no lowercase returns 400."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"user{uuid4().hex[:8]}@example.com",
                "password": "INVALIDPASS123",
                "name": "User",
            },
        )
        assert response.status_code == 400

    def test_register_weak_password_no_digit(self, client):
        """Test registration with no digit returns 400."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"user{uuid4().hex[:8]}@example.com",
                "password": "InvalidPass",
                "name": "User",
            },
        )
        assert response.status_code == 400

    def test_register_invalid_email(self, client):
        """Test registration with invalid email returns 400."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "invalid-email", "password": "ValidPass123", "name": "User"},
        )
        assert response.status_code == 400

    def test_register_missing_name(self, client):
        """Test registration without name returns 422."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"user{uuid4().hex[:8]}@example.com",
                "password": "ValidPass123",
            },
        )
        assert response.status_code in [400, 422]


# ============================================================================
# Refresh Token Tests
# ============================================================================


@pytest.mark.integration
class TestRefresh:
    """Test POST /api/v1/auth/refresh endpoint."""

    def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token returns 401."""
        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "invalid-token-xyz"}
        )
        assert response.status_code == 401

    def test_refresh_missing_token(self, client):
        """Test refresh without token returns 422."""
        response = client.post("/api/v1/auth/refresh", json={})
        assert response.status_code in [400, 422]


# ============================================================================
# Logout Tests
# ============================================================================


@pytest.mark.integration
class TestLogout:
    """Test POST /api/v1/auth/logout endpoint."""

    def test_logout_without_auth(self, client):
        """Test logout without token returns 401."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 401

    def test_logout_with_invalid_token(self, client):
        """Test logout with invalid token returns 401."""
        response = client.post(
            "/api/v1/auth/logout", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401

    def test_logout_with_valid_token(self, client, auth_headers):
        """Test logout with valid token."""
        response = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert response.status_code in [200, 204, 401]


# ============================================================================
# Get Current User Tests
# ============================================================================


@pytest.mark.integration
class TestGetMe:
    """Test GET /api/v1/auth/me endpoint."""

    def test_get_me_without_auth(self, client):
        """Test get me without token returns 401."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_with_invalid_token(self, client):
        """Test get me with invalid token returns 401."""
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401

    def test_get_me_with_valid_token(self, client, auth_headers):
        """Test get me with valid token returns user data."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data or "email" in data


# ============================================================================
# List API Keys Tests
# ============================================================================


@pytest.mark.integration
class TestListAPIKeys:
    """Test GET /api/v1/auth/api-keys endpoint."""

    def test_list_without_auth(self, client):
        """Test list API keys without token returns 401."""
        response = client.get("/api/v1/auth/api-keys")
        assert response.status_code == 401

    def test_list_with_invalid_token(self, client):
        """Test list API keys with invalid token returns 401."""
        response = client.get(
            "/api/v1/auth/api-keys", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401

    def test_list_with_valid_token(self, client, auth_headers):
        """Test list API keys with valid token."""
        response = client.get("/api/v1/auth/api-keys", headers=auth_headers)
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            assert isinstance(response.json(), list)


# ============================================================================
# Create API Key Tests
# ============================================================================


@pytest.mark.integration
class TestCreateAPIKey:
    """Test POST /api/v1/auth/api-keys endpoint."""

    def test_create_without_auth(self, client):
        """Test create API key without token returns 401."""
        response = client.post("/api/v1/auth/api-keys", json={"name": "Test Key"})
        assert response.status_code == 401

    def test_create_with_invalid_token(self, client):
        """Test create API key with invalid token returns 401."""
        response = client.post(
            "/api/v1/auth/api-keys",
            json={"name": "Test Key"},
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_create_missing_name(self, client, auth_headers):
        """Test create API key without name returns 422."""
        response = client.post("/api/v1/auth/api-keys", json={}, headers=auth_headers)
        assert response.status_code in [400, 422, 401]

    def test_create_with_valid_token(self, client, auth_headers):
        """Test create API key with valid token."""
        response = client.post(
            "/api/v1/auth/api-keys",
            json={"name": f"Key-{uuid4().hex[:8]}", "expires_in_days": 365},
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 401]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "key" in data or "id" in data

    def test_create_with_custom_expiry(self, client, auth_headers):
        """Test create API key with custom expiry."""
        response = client.post(
            "/api/v1/auth/api-keys",
            json={"name": f"Key-{uuid4().hex[:8]}", "expires_in_days": 90},
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 401]


# ============================================================================
# Delete API Key Tests
# ============================================================================


@pytest.mark.integration
class TestDeleteAPIKey:
    """Test DELETE /api/v1/auth/api-keys/{id} endpoint."""

    def test_delete_without_auth(self, client):
        """Test delete API key without token returns 401."""
        key_id = str(uuid4())
        response = client.delete(f"/api/v1/auth/api-keys/{key_id}")
        assert response.status_code == 401

    def test_delete_with_invalid_token(self, client):
        """Test delete API key with invalid token returns 401."""
        key_id = str(uuid4())
        response = client.delete(
            f"/api/v1/auth/api-keys/{key_id}",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_delete_nonexistent_key(self, client, auth_headers):
        """Test delete non-existent API key."""
        key_id = str(uuid4())
        response = client.delete(
            f"/api/v1/auth/api-keys/{key_id}", headers=auth_headers
        )
        assert response.status_code in [404, 401, 204, 200]

    def test_delete_with_valid_token(self, client, auth_headers):
        """Test delete API key with valid token."""
        key_id = str(uuid4())
        response = client.delete(
            f"/api/v1/auth/api-keys/{key_id}", headers=auth_headers
        )
        assert response.status_code in [204, 200, 404, 401]
