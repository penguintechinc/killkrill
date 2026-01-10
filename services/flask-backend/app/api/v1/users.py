"""
KillKrill Flask Backend - Users Blueprint

REST API endpoints for user management with full database integration.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

import structlog
from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from passlib.hash import bcrypt
from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

from app.models.db_init import get_engine

logger = structlog.get_logger()

# Create users blueprint
users_bp = Blueprint("users", __name__, url_prefix="/users")


# ============================================================================
# Pydantic Schemas
# ============================================================================


class UserCreateRequest(BaseModel):
    """User creation request."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(
        min_length=8, max_length=256, description="User password (minimum 8 chars)"
    )
    name: str = Field(min_length=1, max_length=255, description="User full name")
    role: Optional[str] = Field(default="viewer", description="User role")

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

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role."""
        allowed_roles = ["viewer", "editor", "admin"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class UserUpdateRequest(BaseModel):
    """User update request."""

    email: Optional[EmailStr] = Field(default=None, description="User email address")
    name: Optional[str] = Field(
        default=None, min_length=1, max_length=255, description="User full name"
    )
    role: Optional[str] = Field(default=None, description="User role")
    is_active: Optional[bool] = Field(default=None, description="User active status")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validate role."""
        if v is not None:
            allowed_roles = ["viewer", "editor", "admin"]
            if v not in allowed_roles:
                raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


# ============================================================================
# Helper Functions
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hash(password)


def get_user_by_id(db, user_id: str) -> Optional[dict]:
    """Get user by ID."""
    user = db(db.users.id == user_id).select().first()
    return user.as_dict() if user else None


def get_user_by_email(db, email: str) -> Optional[dict]:
    """Get user by email."""
    user = db(db.users.email == email).select().first()
    return user.as_dict() if user else None


# ============================================================================
# Routes
# ============================================================================


@users_bp.route("", methods=["GET"])
@users_bp.route("/", methods=["GET"])
@jwt_required()
def list_users():
    """
    List all users with pagination.

    Query params:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    - role: Filter by role
    - is_active: Filter by active status (true/false)
    """
    try:
        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
        role_filter = request.args.get("role")
        is_active_filter = request.args.get("is_active")

        db = get_engine()

        # Build query
        query = db.users.id > 0  # Base query

        if role_filter:
            query &= db.users.role == role_filter

        if is_active_filter is not None:
            is_active = is_active_filter.lower() == "true"
            query &= db.users.is_active == is_active

        # Get total count
        total = db(query).count()

        # Get paginated results
        offset = (page - 1) * per_page
        users = db(query).select(
            orderby=~db.users.created_at, limitby=(offset, offset + per_page)
        )

        user_list = [
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
            }
            for user in users
        ]

        pages = (total + per_page - 1) // per_page

        logger.info(
            "users_listed",
            total=total,
            page=page,
            per_page=per_page,
            correlation_id=g.get("correlation_id"),
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "users": user_list,
                        "total": total,
                        "page": page,
                        "per_page": per_page,
                        "pages": pages,
                    },
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(
            "list_users_error", error=str(e), correlation_id=g.get("correlation_id")
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to list users",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            500,
        )


@users_bp.route("/<user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id: str):
    """Get user by ID."""
    try:
        db = get_engine()
        user = get_user_by_id(db, user_id)

        if not user:
            logger.warning(
                "user_not_found",
                user_id=user_id,
                correlation_id=g.get("correlation_id"),
            )
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

        # Remove sensitive data
        user_data = {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "is_active": user["is_active"],
            "created_at": user["created_at"].isoformat(),
            "updated_at": user["updated_at"].isoformat(),
        }

        logger.info(
            "user_retrieved", user_id=user_id, correlation_id=g.get("correlation_id")
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": user_data,
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(
            "get_user_error",
            error=str(e),
            user_id=user_id,
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to retrieve user",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            500,
        )


@users_bp.route("", methods=["POST"])
@users_bp.route("/", methods=["POST"])
@jwt_required()
def create_user():
    """Create new user (requires admin role)."""
    try:
        data = request.get_json() or {}
        req = UserCreateRequest(**data)
    except ValidationError as e:
        logger.warning(
            "user_create_validation_error",
            errors=e.errors(),
            correlation_id=g.get("correlation_id"),
        )
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

    try:
        db = get_engine()

        # Check if user already exists
        existing_user = get_user_by_email(db, req.email)
        if existing_user:
            logger.warning(
                "user_create_duplicate_email",
                email=req.email,
                correlation_id=g.get("correlation_id"),
            )
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
        user_id = str(uuid4())
        hashed_password = hash_password(req.password)

        db.users.insert(
            id=user_id,
            email=req.email,
            password_hash=hashed_password,
            name=req.name,
            role=req.role,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.commit()

        user = get_user_by_id(db, user_id)

        logger.info(
            "user_created",
            user_id=user_id,
            email=req.email,
            correlation_id=g.get("correlation_id"),
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
                        "is_active": user["is_active"],
                        "created_at": user["created_at"].isoformat(),
                    },
                    "message": "User created successfully",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(
            "create_user_error", error=str(e), correlation_id=g.get("correlation_id")
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to create user",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            500,
        )


@users_bp.route("/<user_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_user(user_id: str):
    """Update user (requires admin role or self)."""
    try:
        data = request.get_json() or {}
        req = UserUpdateRequest(**data)
    except ValidationError as e:
        logger.warning(
            "user_update_validation_error",
            errors=e.errors(),
            correlation_id=g.get("correlation_id"),
        )
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

    try:
        db = get_engine()
        user = get_user_by_id(db, user_id)

        if not user:
            logger.warning(
                "user_update_not_found",
                user_id=user_id,
                correlation_id=g.get("correlation_id"),
            )
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

        # Build update dict
        update_data = {"updated_at": datetime.utcnow()}

        if req.email is not None:
            # Check email not taken by another user
            existing = get_user_by_email(db, req.email)
            if existing and existing["id"] != user_id:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Email already in use",
                            "correlation_id": g.get("correlation_id"),
                        }
                    ),
                    409,
                )
            update_data["email"] = req.email

        if req.name is not None:
            update_data["name"] = req.name

        if req.role is not None:
            update_data["role"] = req.role

        if req.is_active is not None:
            update_data["is_active"] = req.is_active

        # Update user
        db(db.users.id == user_id).update(**update_data)
        db.commit()

        updated_user = get_user_by_id(db, user_id)

        logger.info(
            "user_updated", user_id=user_id, correlation_id=g.get("correlation_id")
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "id": updated_user["id"],
                        "email": updated_user["email"],
                        "name": updated_user["name"],
                        "role": updated_user["role"],
                        "is_active": updated_user["is_active"],
                        "updated_at": updated_user["updated_at"].isoformat(),
                    },
                    "message": "User updated successfully",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(
            "update_user_error",
            error=str(e),
            user_id=user_id,
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to update user",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            500,
        )


@users_bp.route("/<user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id: str):
    """Soft delete user (requires admin role)."""
    try:
        db = get_engine()
        user = get_user_by_id(db, user_id)

        if not user:
            logger.warning(
                "user_delete_not_found",
                user_id=user_id,
                correlation_id=g.get("correlation_id"),
            )
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

        # Soft delete - set is_active to False
        db(db.users.id == user_id).update(is_active=False, updated_at=datetime.utcnow())
        db.commit()

        logger.info(
            "user_deleted", user_id=user_id, correlation_id=g.get("correlation_id")
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "User deleted successfully",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(
            "delete_user_error",
            error=str(e),
            user_id=user_id,
            correlation_id=g.get("correlation_id"),
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to delete user",
                    "correlation_id": g.get("correlation_id"),
                }
            ),
            500,
        )


__all__ = ["users_bp"]
