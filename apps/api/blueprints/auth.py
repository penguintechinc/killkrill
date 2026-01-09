"""
KillKrill API - Authentication Blueprint
Login, logout, token management endpoints
"""

import hashlib
from datetime import datetime, timedelta

import structlog
from middleware.auth import (
    generate_api_key, generate_jwt_token, generate_refresh_token, hash_api_key,
    hash_password, require_auth, verify_password,
)
from models.database import get_db
from quart import Blueprint, g, jsonify, request

from config import get_config

logger = structlog.get_logger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
async def login():
    """
    User login endpoint

    Request body:
        email: User email
        password: User password

    Returns:
        access_token: JWT access token
        refresh_token: Refresh token for getting new access tokens
        user: User information
    """
    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Find user by email
    user = db(db.users.email == email).select().first()

    if not user:
        logger.warning("login_failed", reason="user_not_found", email=email)
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        logger.warning("login_failed", reason="user_inactive", email=email)
        return jsonify({"error": "Account is disabled"}), 401

    # Verify password
    if not verify_password(password, user.password_hash):
        logger.warning("login_failed", reason="invalid_password", email=email)
        return jsonify({"error": "Invalid credentials"}), 401

    # Generate tokens
    config = get_config()
    access_token = generate_jwt_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    refresh_token = generate_refresh_token()
    refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # Store refresh token
    db.refresh_tokens.insert(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.utcnow()
        + timedelta(seconds=config.JWT_REFRESH_TOKEN_EXPIRES),
    )

    # Update last login
    user.update_record(last_login=datetime.utcnow())
    db.commit()

    logger.info("login_success", user_id=user.id, username=user.username)

    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": config.JWT_ACCESS_TOKEN_EXPIRES,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            },
        }
    )


@auth_bp.route("/register", methods=["POST"])
async def register():
    """
    User registration endpoint

    Request body:
        username: Unique username
        email: User email
        password: Password (min 8 characters)
        first_name: First name
        last_name: Last name
    """
    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    required_fields = ["username", "email", "password"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    # Validate password strength
    password = data.get("password")
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Check if username or email already exists
    existing = (
        db(
            (db.users.username == data.get("username"))
            | (db.users.email == data.get("email"))
        )
        .select()
        .first()
    )

    if existing:
        if existing.username == data.get("username"):
            return jsonify({"error": "Username already taken"}), 409
        else:
            return jsonify({"error": "Email already registered"}), 409

    # Create user
    user_id = db.users.insert(
        username=data.get("username"),
        email=data.get("email"),
        password_hash=hash_password(password),
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        role="user",
        is_active=True,
    )
    db.commit()

    logger.info("user_registered", user_id=user_id, username=data.get("username"))

    return (
        jsonify(
            {
                "message": "Registration successful",
                "user_id": user_id,
            }
        ),
        201,
    )


@auth_bp.route("/refresh", methods=["POST"])
async def refresh():
    """
    Refresh access token using refresh token

    Request body:
        refresh_token: Valid refresh token
    """
    data = await request.get_json()

    if not data or not data.get("refresh_token"):
        return jsonify({"error": "Refresh token required"}), 400

    refresh_token = data.get("refresh_token")
    refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Find valid refresh token
    token_record = (
        db(
            (db.refresh_tokens.token_hash == refresh_token_hash)
            & (db.refresh_tokens.revoked == False)
            & (db.refresh_tokens.expires_at > datetime.utcnow())
        )
        .select()
        .first()
    )

    if not token_record:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    # Get user
    user = db(db.users.id == token_record.user_id).select().first()
    if not user or not user.is_active:
        return jsonify({"error": "User not found or inactive"}), 401

    # Generate new access token
    config = get_config()
    access_token = generate_jwt_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    logger.info("token_refreshed", user_id=user.id)

    return jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": config.JWT_ACCESS_TOKEN_EXPIRES,
        }
    )


@auth_bp.route("/logout", methods=["POST"])
@require_auth()
async def logout():
    """
    Logout and revoke refresh tokens

    Request body (optional):
        refresh_token: Specific token to revoke
        all: True to revoke all user tokens
    """
    data = await request.get_json() or {}
    user_id = g.auth.get("user_id")

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    if data.get("all"):
        # Revoke all user tokens
        db(
            (db.refresh_tokens.user_id == user_id)
            & (db.refresh_tokens.revoked == False)
        ).update(revoked=True, revoked_at=datetime.utcnow())
        db.commit()
        logger.info("all_tokens_revoked", user_id=user_id)
    elif data.get("refresh_token"):
        # Revoke specific token
        token_hash = hashlib.sha256(data.get("refresh_token").encode()).hexdigest()
        db(
            (db.refresh_tokens.token_hash == token_hash)
            & (db.refresh_tokens.user_id == user_id)
        ).update(revoked=True, revoked_at=datetime.utcnow())
        db.commit()
        logger.info("token_revoked", user_id=user_id)

    return jsonify({"message": "Logged out successfully"})


@auth_bp.route("/me", methods=["GET"])
@require_auth()
async def get_me():
    """Get current user information"""
    user_id = g.auth.get("user_id")

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    user = db(db.users.id == user_id).select().first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }
    )


@auth_bp.route("/api-keys", methods=["GET"])
@require_auth()
async def list_api_keys():
    """List user's API keys"""
    user_id = g.auth.get("user_id")

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    keys = db(
        (db.api_keys.user_id == user_id) & (db.api_keys.is_active == True)
    ).select()

    return jsonify(
        {
            "api_keys": [
                {
                    "id": key.id,
                    "name": key.name,
                    "created_at": (
                        key.created_at.isoformat() if key.created_at else None
                    ),
                    "expires_at": (
                        key.expires_at.isoformat() if key.expires_at else None
                    ),
                    "last_used": key.last_used.isoformat() if key.last_used else None,
                }
                for key in keys
            ]
        }
    )


@auth_bp.route("/api-keys", methods=["POST"])
@require_auth()
async def create_api_key():
    """
    Create a new API key

    Request body:
        name: Key name/description
        expires_days: Optional expiration in days
        permissions: Optional list of permissions
    """
    data = await request.get_json() or {}
    user_id = g.auth.get("user_id")

    if not data.get("name"):
        return jsonify({"error": "Key name required"}), 400

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Generate API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)

    # Calculate expiration
    expires_at = None
    if data.get("expires_days"):
        expires_at = datetime.utcnow() + timedelta(days=int(data.get("expires_days")))

    # Store permissions as JSON
    import json

    permissions = json.dumps(data.get("permissions", ["read"]))

    # Insert key
    key_id = db.api_keys.insert(
        user_id=user_id,
        name=data.get("name"),
        key_hash=key_hash,
        permissions=permissions,
        expires_at=expires_at,
    )
    db.commit()

    logger.info("api_key_created", user_id=user_id, key_id=key_id)

    # Return the key only once - it cannot be retrieved later
    return (
        jsonify(
            {
                "id": key_id,
                "name": data.get("name"),
                "api_key": api_key,  # Only returned on creation
                "expires_at": expires_at.isoformat() if expires_at else None,
                "message": "Store this API key securely - it cannot be retrieved later",
            }
        ),
        201,
    )


@auth_bp.route("/api-keys/<int:key_id>", methods=["DELETE"])
@require_auth()
async def delete_api_key(key_id: int):
    """Delete/revoke an API key"""
    user_id = g.auth.get("user_id")

    db = await get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    # Verify ownership and deactivate
    result = db((db.api_keys.id == key_id) & (db.api_keys.user_id == user_id)).update(
        is_active=False
    )
    db.commit()

    if not result:
        return jsonify({"error": "API key not found"}), 404

    logger.info("api_key_deleted", user_id=user_id, key_id=key_id)

    return jsonify({"message": "API key deleted"})
