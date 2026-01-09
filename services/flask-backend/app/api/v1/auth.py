"""
KillKrill Flask Backend - Authentication Blueprint

Provides JWT-based authentication endpoints including login, register,
token refresh, logout, user info, and API key management.
"""

from datetime import datetime, timedelta
from functools import wraps
from typing import Optional
from uuid import uuid4

import structlog
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from passlib.hash import bcrypt
from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

from app.models.db_init import get_engine

logger = structlog.get_logger()

# Create authentication blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Token blacklist (in-memory - replace with Redis in production)
revoked_tokens = set()


# ============================================================================
# Pydantic Schemas
# ============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(
        min_length=8, max_length=256, description="User password (minimum 8 chars)"
    )
    name: str = Field(min_length=1, max_length=255, description="User full name")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(min_length=8, max_length=256, description="User password")


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(description="Refresh token")


class APIKeyCreateRequest(BaseModel):
    """API key creation request."""

    name: str = Field(min_length=1, max_length=255, description="API key name")
    expires_in_days: Optional[int] = Field(
        default=365, ge=1, le=3650, description="Expiration in days (1-3650)"
    )


# ============================================================================
# Decorators
# ============================================================================


def auth_required(fn):
    """Decorator to require JWT authentication."""

    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        # Check if token is revoked
        jti = get_jwt().get("jti")
        if jti in revoked_tokens:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Token has been revoked",
                        "correlation_id": g.get("correlation_id"),
                    }
                ),
                401,
            )
        return fn(*args, **kwargs)

    return wrapper


# ============================================================================
# Helper Functions
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.verify(password, hashed)


def get_user_by_email(db, email: str) -> Optional[dict]:
    """Get user by email address."""
    user = db(db.users.email == email).select().first()
    return user.as_dict() if user else None


def get_user_by_id(db, user_id: str) -> Optional[dict]:
    """Get user by ID."""
    user = db(db.users.id == user_id).select().first()
    return user.as_dict() if user else None


def create_user(db, email: str, password: str, name: str) -> dict:
    """Create a new user."""
    user_id = str(uuid4())
    hashed_password = hash_password(password)

    db.users.insert(
        id=user_id,
        email=email,
        password_hash=hashed_password,
        name=name,
        role="viewer",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.commit()

    return get_user_by_id(db, user_id)


def create_api_key_record(
    db, user_id: str, name: str, key: str, expires_in_days: int
) -> dict:
    """Create an API key record."""
    key_id = str(uuid4())
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    db.api_keys.insert(
        id=key_id,
        user_id=user_id,
        name=name,
        key_hash=hash_password(key),
        expires_at=expires_at,
        created_at=datetime.utcnow(),
    )
    db.commit()

    return {
        "id": key_id,
        "name": name,
        "key": key,  # Return plaintext key only on creation
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Routes
# ============================================================================


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    User login endpoint.

    Returns JWT access and refresh tokens.
    """
    try:
        data = request.get_json() or {}
        req = LoginRequest(**data)
    except ValidationError as e:
        logger.warning("login_validation_error", errors=e.errors())
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Invalid request data",
                    "details": e.errors(),
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            400,
        )

    db = get_engine()
    user = get_user_by_email(db, req.email)

    if not user or not verify_password(req.password, user["password_hash"]):
        logger.warning("login_failed", email=req.email)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Invalid email or password",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            401,
        )

    # Create tokens
    access_token = create_access_token(identity=user["id"])
    refresh_token = create_refresh_token(identity=user["id"])

    logger.info("login_success", user_id=user["id"], email=user["email"])

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                    "expires_in": 3600,  # 1 hour
                    "user": {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user["name"],
                        "role": user["role"],
                    },
                },
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    User registration endpoint.

    Creates a new user account.
    """
    try:
        data = request.get_json() or {}
        req = RegisterRequest(**data)
    except ValidationError as e:
        logger.warning("register_validation_error", errors=e.errors())
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Invalid request data",
                    "details": e.errors(),
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            400,
        )

    db = get_engine()

    # Check if user already exists
    existing_user = get_user_by_email(db, req.email)
    if existing_user:
        logger.warning("register_duplicate_email", email=req.email)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "User with this email already exists",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            409,
        )

    # Create user
    user = create_user(db, req.email, req.password, req.name)

    logger.info("register_success", user_id=user["id"], email=user["email"])

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "user": {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user["name"],
                        "role": user["role"],
                        "created_at": user["created_at"].isoformat(),
                    }
                },
                "message": "User registered successfully",
                "correlation_id": g.get("correlation_id"),
            }
        ),
        201,
    )


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Token refresh endpoint.

    Returns a new access token using a valid refresh token.
    """
    # Check if refresh token is revoked
    jti = get_jwt().get("jti")
    if jti in revoked_tokens:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Refresh token has been revoked",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            401,
        )

    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)

    logger.info("token_refreshed", user_id=user_id)

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@auth_bp.route("/logout", methods=["POST"])
@auth_required
def logout():
    """
    Logout endpoint.

    Revokes the current access token.
    """
    jti = get_jwt().get("jti")
    revoked_tokens.add(jti)

    user_id = get_jwt_identity()
    logger.info("logout_success", user_id=user_id)

    return (
        jsonify(
            {
                "success": True,
                "message": "Successfully logged out",
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@auth_bp.route("/me", methods=["GET"])
@auth_required
def get_current_user():
    """
    Get current user information.

    Returns the authenticated user's profile.
    """
    user_id = get_jwt_identity()
    db = get_engine()
    user = get_user_by_id(db, user_id)

    if not user:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "User not found",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            404,
        )

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "role": user["role"],
                    "created_at": user["created_at"].isoformat(),
                    "updated_at": user["updated_at"].isoformat(),
                },
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@auth_bp.route("/api-keys", methods=["GET"])
@auth_required
def list_api_keys():
    """
    List user's API keys.

    Returns all API keys for the authenticated user (excluding key values).
    """
    user_id = get_jwt_identity()
    db = get_engine()

    keys = db(db.api_keys.user_id == user_id).select(
        db.api_keys.id,
        db.api_keys.name,
        db.api_keys.expires_at,
        db.api_keys.created_at,
        orderby=~db.api_keys.created_at,
    )

    api_keys = [
        {
            "id": key.id,
            "name": key.name,
            "expires_at": key.expires_at.isoformat(),
            "created_at": key.created_at.isoformat(),
        }
        for key in keys
    ]

    return (
        jsonify(
            {
                "success": True,
                "data": {"api_keys": api_keys, "total": len(api_keys)},
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


@auth_bp.route("/api-keys", methods=["POST"])
@auth_required
def create_api_key():
    """
    Create a new API key.

    Returns the newly created API key (plaintext key only shown once).
    """
    try:
        data = request.get_json() or {}
        req = APIKeyCreateRequest(**data)
    except ValidationError as e:
        logger.warning("api_key_validation_error", errors=e.errors())
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Invalid request data",
                    "details": e.errors(),
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            400,
        )

    user_id = get_jwt_identity()
    db = get_engine()

    # Generate API key
    api_key = f"kk_{uuid4().hex}"

    # Create API key record
    key_record = create_api_key_record(
        db, user_id, req.name, api_key, req.expires_in_days or 365
    )

    logger.info("api_key_created", user_id=user_id, key_id=key_record["id"])

    return (
        jsonify(
            {
                "success": True,
                "data": key_record,
                "message": "API key created successfully. Save this key - it won't be shown again.",
                "correlation_id": g.get("correlation_id"),
            }
        ),
        201,
    )


@auth_bp.route("/api-keys/<key_id>", methods=["DELETE"])
@auth_required
def delete_api_key(key_id: str):
    """
    Delete an API key.

    Removes the specified API key if it belongs to the authenticated user.
    """
    user_id = get_jwt_identity()
    db = get_engine()

    # Check if key exists and belongs to user
    key = db((db.api_keys.id == key_id) & (db.api_keys.user_id == user_id)).select()

    if not key:
        logger.warning("api_key_not_found", user_id=user_id, key_id=key_id)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "API key not found",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            404,
        )

    # Delete the key
    db((db.api_keys.id == key_id) & (db.api_keys.user_id == user_id)).delete()
    db.commit()

    logger.info("api_key_deleted", user_id=user_id, key_id=key_id)

    return (
        jsonify(
            {
                "success": True,
                "message": "API key deleted successfully",
                "correlation_id": g.get("correlation_id"),
            }
        ),
        200,
    )


__all__ = ["auth_bp", "auth_required"]
