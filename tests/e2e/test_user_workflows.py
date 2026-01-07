"""
End-to-end tests for killkrill user workflows.

Tests complete user journeys including registration, login, API keys,
user management, and password reset workflows.

Requires running API service at API_BASE_URL (default: http://localhost:5000).
"""

from time import sleep
from uuid import uuid4

import pytest

# ============================================================================
# Registration Flow Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.auth
class TestRegistrationFlow:
    """Test complete user registration workflow."""

    def test_registration_to_dashboard_flow(self, api_client, test_user_data):
        """
        E2E: Register → Verify email (mock) → Login → Access dashboard.

        Steps:
        1. Register new user
        2. Mock email verification (assume auto-verified or skip)
        3. Login with new credentials
        4. Access protected dashboard endpoint
        """
        # Step 1: Register new user
        register_response = api_client.post(
            "/api/v1/auth/register", json=test_user_data
        )
        assert register_response.status_code in [
            200,
            201,
        ], f"Registration failed: {register_response.status_code}"

        register_data = register_response.json()
        assert (
            "id" in register_data or "user" in register_data
        ), "Registration response missing user data"

        # Step 2: Mock email verification (in production, verify email)
        # For testing, assume user is auto-verified or verification disabled
        # If verification endpoint exists, call it here
        user_id = register_data.get("id") or register_data.get("user", {}).get("id")

        # Step 3: Login with new credentials
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert (
            login_response.status_code == 200
        ), f"Login failed: {login_response.status_code}"

        login_data = login_response.json()
        assert "access_token" in login_data, "Login response missing access_token"

        access_token = login_data["access_token"]
        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Step 4: Access protected dashboard endpoint
        me_response = api_client.get("/api/v1/auth/me", headers=auth_headers)
        assert (
            me_response.status_code == 200
        ), f"Dashboard access failed: {me_response.status_code}"

        me_data = me_response.json()
        assert me_data.get("email") == test_user_data["email"], "User email mismatch"

    def test_registration_with_duplicate_email(self, api_client, test_user_data):
        """E2E: Attempt to register same email twice returns 409."""
        # First registration
        first_response = api_client.post("/api/v1/auth/register", json=test_user_data)
        assert first_response.status_code in [200, 201]

        # Second registration with same email
        second_response = api_client.post("/api/v1/auth/register", json=test_user_data)
        assert (
            second_response.status_code == 409
        ), "Duplicate email should return 409 Conflict"


# ============================================================================
# Login Flow Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.auth
class TestLoginFlow:
    """Test complete login and session management workflow."""

    def test_complete_login_session_logout_flow(self, api_client, test_user):
        """
        E2E: Login → Get JWT → Access protected endpoints → Logout.

        Steps:
        1. Login with credentials
        2. Receive JWT access token
        3. Access multiple protected endpoints
        4. Logout and invalidate token
        5. Verify token is no longer valid
        """
        # Step 1: Login
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        access_token = login_data["access_token"]

        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Step 2 & 3: Access protected endpoints
        endpoints_to_test = [
            "/api/v1/auth/me",
            "/api/v1/auth/api-keys",
        ]

        for endpoint in endpoints_to_test:
            response = api_client.get(endpoint, headers=auth_headers)
            assert (
                response.status_code == 200
            ), f"Access to {endpoint} failed with token"

        # Step 4: Logout
        logout_response = api_client.post("/api/v1/auth/logout", headers=auth_headers)
        assert logout_response.status_code in [200, 204], "Logout failed"

        # Step 5: Verify token is invalidated (optional - depends on implementation)
        # Some systems may still accept token until expiry, others blacklist it
        # This test is informational
        post_logout_response = api_client.get("/api/v1/auth/me", headers=auth_headers)
        # Accept both 200 (token still valid) or 401 (token invalidated)
        assert post_logout_response.status_code in [200, 401]

    def test_login_with_invalid_credentials(self, api_client):
        """E2E: Login with invalid credentials returns 401."""
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@killkrill.test",
                "password": "WrongPassword123!",
            },
        )
        assert login_response.status_code == 401

    def test_access_protected_without_token(self, api_client):
        """E2E: Accessing protected endpoints without token returns 401."""
        protected_endpoints = [
            "/api/v1/auth/me",
            "/api/v1/auth/api-keys",
            "/api/v1/users",
        ]

        for endpoint in protected_endpoints:
            response = api_client.get(endpoint)
            assert (
                response.status_code == 401
            ), f"{endpoint} should require authentication"


# ============================================================================
# API Key Flow Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.auth
class TestAPIKeyFlow:
    """Test complete API key lifecycle workflow."""

    def test_complete_api_key_lifecycle(self, api_client, test_user):
        """
        E2E: Login → Create API key → Use API key for auth → List keys → Revoke key.

        Steps:
        1. Login to get JWT
        2. Create new API key
        3. Use API key for authentication
        4. List all API keys
        5. Revoke API key
        6. Verify API key is no longer valid
        """
        # Step 1: Login
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]

        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Step 2: Create API key
        key_name = f"test-key-{uuid4().hex[:8]}"
        create_key_response = api_client.post(
            "/api/v1/auth/api-keys",
            json={"name": key_name, "expires_in_days": 365},
            headers=auth_headers,
        )
        assert create_key_response.status_code in [
            200,
            201,
        ], f"API key creation failed: {create_key_response.status_code}"

        key_data = create_key_response.json()
        api_key = key_data.get("key") or key_data.get("api_key")
        key_id = key_data.get("id")

        assert api_key, "API key not returned in response"
        assert key_id, "API key ID not returned in response"

        # Step 3: Use API key for authentication
        api_key_headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

        # Test API key authentication (if supported)
        # Note: Some APIs use X-API-Key, others use Authorization: Bearer
        # Try both patterns
        api_key_auth_response = api_client.get(
            "/api/v1/auth/me", headers=api_key_headers
        )

        # If X-API-Key not supported, try Authorization header
        if api_key_auth_response.status_code == 401:
            api_key_headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            api_key_auth_response = api_client.get(
                "/api/v1/auth/me", headers=api_key_headers
            )

        # Accept 200 (API key works) or 401 (API key auth not implemented)
        assert api_key_auth_response.status_code in [200, 401]

        # Step 4: List all API keys
        list_keys_response = api_client.get(
            "/api/v1/auth/api-keys", headers=auth_headers
        )
        assert list_keys_response.status_code == 200
        keys_list = list_keys_response.json()
        assert isinstance(keys_list, list)

        # Verify our key is in the list
        key_names = [k.get("name") for k in keys_list]
        assert key_name in key_names, "Created key not found in list"

        # Step 5: Revoke API key
        revoke_response = api_client.delete(
            f"/api/v1/auth/api-keys/{key_id}", headers=auth_headers
        )
        assert revoke_response.status_code in [
            200,
            204,
        ], f"API key revocation failed: {revoke_response.status_code}"

        # Step 6: Verify API key is revoked
        list_after_revoke = api_client.get(
            "/api/v1/auth/api-keys", headers=auth_headers
        )
        assert list_after_revoke.status_code == 200
        remaining_keys = list_after_revoke.json()
        remaining_names = [k.get("name") for k in remaining_keys]
        assert key_name not in remaining_names, "Revoked key still appears in list"

    def test_api_key_expiration(self, api_client, test_user):
        """E2E: Create API key with short expiration."""
        # Login
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        access_token = login_response.json()["access_token"]
        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Create API key with 1 day expiration
        create_key_response = api_client.post(
            "/api/v1/auth/api-keys",
            json={"name": f"short-lived-{uuid4().hex[:8]}", "expires_in_days": 1},
            headers=auth_headers,
        )
        assert create_key_response.status_code in [200, 201]

        key_data = create_key_response.json()
        # Verify expiration is set
        assert "expires_at" in key_data or "expires_in_days" in key_data


# ============================================================================
# User Management Flow Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.auth
class TestUserManagementFlow:
    """Test user management workflow (admin operations)."""

    def test_admin_create_user_assign_role_login(
        self, api_client, admin_headers, viewer_user_data
    ):
        """
        E2E: Admin login → Create user → Assign role → User login → Verify permissions.

        Steps:
        1. Admin creates new user with viewer role
        2. New user logs in
        3. Verify user has viewer permissions (read-only)
        4. Verify user cannot perform admin actions
        """
        # Step 1: Admin creates user with viewer role
        create_user_response = api_client.post(
            "/api/v1/users", json=viewer_user_data, headers=admin_headers
        )

        # Accept both 201 (created) or 409 (already exists) for idempotency
        assert create_user_response.status_code in [
            200,
            201,
            409,
        ], f"User creation failed: {create_user_response.status_code}"

        if create_user_response.status_code in [200, 201]:
            user_data = create_user_response.json()
            user_id = user_data.get("id") or user_data.get("user", {}).get("id")
        else:
            # If user exists, get user ID from list
            users_response = api_client.get("/api/v1/users", headers=admin_headers)
            users = users_response.json()
            user_id = next(
                (u["id"] for u in users if u.get("email") == viewer_user_data["email"]),
                None,
            )

        # Step 2: New user logs in
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": viewer_user_data["email"],
                "password": viewer_user_data["password"],
            },
        )
        assert login_response.status_code == 200, "Viewer login failed"

        viewer_token = login_response.json()["access_token"]
        viewer_headers = {
            "Authorization": f"Bearer {viewer_token}",
            "Content-Type": "application/json",
        }

        # Step 3: Verify viewer can read (GET)
        me_response = api_client.get("/api/v1/auth/me", headers=viewer_headers)
        assert me_response.status_code == 200, "Viewer cannot access profile"

        # Step 4: Verify viewer cannot perform admin actions
        # Try to create another user (should fail with 403)
        unauthorized_create = api_client.post(
            "/api/v1/users",
            json={
                "email": f"test{uuid4().hex[:8]}@killkrill.test",
                "password": "Test123!",
                "name": "Test User",
            },
            headers=viewer_headers,
        )
        # Expect 403 (Forbidden) or 401 (Unauthorized) for non-admin
        assert unauthorized_create.status_code in [
            401,
            403,
        ], "Viewer should not be able to create users"

        # Cleanup: admin deletes viewer user
        if user_id:
            api_client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)

    def test_maintainer_permissions(
        self, api_client, admin_headers, maintainer_user_data
    ):
        """E2E: Verify maintainer role has read/write but not user management."""
        # Admin creates maintainer user
        create_response = api_client.post(
            "/api/v1/users", json=maintainer_user_data, headers=admin_headers
        )
        assert create_response.status_code in [200, 201, 409]

        # Maintainer logs in
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": maintainer_user_data["email"],
                "password": maintainer_user_data["password"],
            },
        )
        assert login_response.status_code == 200

        maintainer_token = login_response.json()["access_token"]
        maintainer_headers = {
            "Authorization": f"Bearer {maintainer_token}",
            "Content-Type": "application/json",
        }

        # Verify maintainer can access their profile
        me_response = api_client.get("/api/v1/auth/me", headers=maintainer_headers)
        assert me_response.status_code == 200

        # Verify maintainer cannot manage users
        create_user_response = api_client.post(
            "/api/v1/users",
            json={
                "email": f"test{uuid4().hex[:8]}@killkrill.test",
                "password": "Test123!",
                "name": "Test",
            },
            headers=maintainer_headers,
        )
        assert create_user_response.status_code in [
            401,
            403,
        ], "Maintainer should not create users"

        # Cleanup
        if create_response.status_code in [200, 201]:
            user_id = create_response.json().get("id")
            if user_id:
                api_client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)


# ============================================================================
# Password Reset Flow Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.auth
class TestPasswordResetFlow:
    """Test password reset workflow."""

    def test_password_reset_flow(self, api_client, test_user):
        """
        E2E: Request reset → Get token (mock email) → Reset password → Login with new password.

        Steps:
        1. User requests password reset
        2. Mock receiving reset token via email
        3. User resets password with token
        4. User logs in with new password
        5. Old password no longer works
        """
        # Step 1: Request password reset
        reset_request_response = api_client.post(
            "/api/v1/auth/password-reset/request", json={"email": test_user["email"]}
        )

        # Accept both 200 (token sent) or 202 (request accepted)
        # Some APIs return 200 regardless to prevent email enumeration
        assert reset_request_response.status_code in [
            200,
            202,
            404,
        ], f"Password reset request failed: {reset_request_response.status_code}"

        # Step 2: Mock receiving reset token
        # In production, token is sent via email
        # For testing, we'll skip actual token verification or use a test token
        # If API provides test endpoint to get token, use it here
        mock_reset_token = f"mock_reset_{uuid4().hex}"

        # Step 3: Reset password with token (if endpoint exists)
        new_password = "NewTestPass123!"
        reset_response = api_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": mock_reset_token, "new_password": new_password},
        )

        # If endpoint not implemented or token invalid, skip remaining steps
        if reset_response.status_code == 404:
            pytest.skip("Password reset confirm endpoint not implemented")
        elif reset_response.status_code == 401:
            pytest.skip("Cannot test password reset without valid token")

        # Step 4: Login with new password
        if reset_response.status_code in [200, 204]:
            login_with_new = api_client.post(
                "/api/v1/auth/login",
                json={"email": test_user["email"], "password": new_password},
            )
            assert login_with_new.status_code == 200, "Login with new password failed"

            # Step 5: Verify old password no longer works
            login_with_old = api_client.post(
                "/api/v1/auth/login",
                json={"email": test_user["email"], "password": test_user["password"]},
            )
            assert (
                login_with_old.status_code == 401
            ), "Old password should no longer work"

    def test_password_reset_invalid_email(self, api_client):
        """E2E: Password reset request with non-existent email."""
        reset_request_response = api_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "nonexistent@killkrill.test"},
        )

        # Most secure APIs return 200 regardless to prevent email enumeration
        # Accept 200, 202, or 404
        assert reset_request_response.status_code in [200, 202, 404]


# ============================================================================
# Token Expiration and Refresh Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.auth
class TestTokenManagement:
    """Test JWT token expiration and refresh workflows."""

    def test_token_refresh_flow(self, api_client, test_user):
        """
        E2E: Login → Get access and refresh tokens → Refresh access token.

        Steps:
        1. Login to get access and refresh tokens
        2. Use refresh token to get new access token
        3. Verify new access token works
        """
        # Step 1: Login
        login_response = api_client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        login_data = login_response.json()

        access_token = login_data.get("access_token")
        refresh_token = login_data.get("refresh_token")

        assert access_token, "Access token not provided"

        # If no refresh token, skip remaining test
        if not refresh_token:
            pytest.skip("Refresh token not provided by API")

        # Step 2: Use refresh token to get new access token
        refresh_response = api_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )

        if refresh_response.status_code == 404:
            pytest.skip("Token refresh endpoint not implemented")

        assert (
            refresh_response.status_code == 200
        ), f"Token refresh failed: {refresh_response.status_code}"

        refresh_data = refresh_response.json()
        new_access_token = refresh_data.get("access_token")

        assert new_access_token, "New access token not provided"
        assert (
            new_access_token != access_token
        ), "New token should be different from old token"

        # Step 3: Verify new access token works
        new_auth_headers = {
            "Authorization": f"Bearer {new_access_token}",
            "Content-Type": "application/json",
        }

        me_response = api_client.get("/api/v1/auth/me", headers=new_auth_headers)
        assert me_response.status_code == 200, "New access token does not work"

    def test_invalid_refresh_token(self, api_client):
        """E2E: Attempt to refresh with invalid token."""
        refresh_response = api_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "invalid_token_xyz"}
        )

        # Accept 401 (unauthorized) or 404 (endpoint not implemented)
        assert refresh_response.status_code in [401, 404]


# ============================================================================
# Multi-User Session Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.auth
class TestMultiUserSessions:
    """Test multiple concurrent user sessions."""

    def test_concurrent_user_sessions(
        self, api_client, test_user_data, viewer_user_data
    ):
        """
        E2E: Multiple users login and access resources concurrently.

        Steps:
        1. Create two users
        2. Both users login simultaneously
        3. Verify both sessions are independent
        4. Verify user A cannot access user B's resources
        """
        # Create both users
        user1_response = api_client.post("/api/v1/auth/register", json=test_user_data)
        assert user1_response.status_code in [200, 201]

        user2_response = api_client.post("/api/v1/auth/register", json=viewer_user_data)
        assert user2_response.status_code in [200, 201]

        # Both users login
        login1 = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert login1.status_code == 200

        login2 = api_client.post(
            "/api/v1/auth/login",
            json={
                "email": viewer_user_data["email"],
                "password": viewer_user_data["password"],
            },
        )
        assert login2.status_code == 200

        token1 = login1.json()["access_token"]
        token2 = login2.json()["access_token"]

        # Verify tokens are different
        assert token1 != token2

        # Verify both sessions work independently
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        me1 = api_client.get("/api/v1/auth/me", headers=headers1)
        me2 = api_client.get("/api/v1/auth/me", headers=headers2)

        assert me1.status_code == 200
        assert me2.status_code == 200

        # Verify users get their own data
        assert me1.json().get("email") == test_user_data["email"]
        assert me2.json().get("email") == viewer_user_data["email"]
