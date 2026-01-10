"""
Pydantic v2 schemas for API request/response validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# ============================================================================
# Enums
# ============================================================================


class RoleEnum(str, Enum):
    """User roles."""

    ADMIN = "admin"
    MAINTAINER = "maintainer"
    VIEWER = "viewer"


class CheckTypeEnum(str, Enum):
    """Sensor check types."""

    TCP = "tcp"
    HTTP = "http"
    HTTPS = "https"
    DNS = "dns"
    ICMP = "icmp"


# ============================================================================
# Common/Generic Schemas
# ============================================================================


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class APIResponse(BaseModel, Generic[TypeVar("T")]):
    """Generic API response wrapper."""

    success: bool = Field(description="Request success status")
    data: Optional[Any] = Field(default=None, description="Response data")
    message: Optional[str] = Field(default=None, description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response schema."""

    success: bool = Field(default=False)
    error: str = Field(description="Error message")
    code: str = Field(description="Error code")
    details: Optional[dict] = Field(default=None, description="Additional details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Auth Schemas
# ============================================================================


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(min_length=8, max_length=256, description="User password")


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(description="Token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(description="Refresh token")

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, v: str) -> str:
        """Validate refresh token is not empty."""
        if not v or not v.strip():
            raise ValueError("refresh_token cannot be empty")
        return v.strip()


# ============================================================================
# User Schemas
# ============================================================================


class UserCreate(BaseModel):
    """User creation request."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(
        min_length=8, max_length=256, description="User password (minimum 8 chars)"
    )
    name: str = Field(min_length=1, max_length=255, description="User full name")
    role: RoleEnum = Field(default=RoleEnum.VIEWER, description="User role")

    @model_validator(mode="after")
    def validate_password_strength(self) -> "UserCreate":
        """Validate password contains uppercase, lowercase, number."""
        password = self.password
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        return self


class UserUpdate(BaseModel):
    """User update request."""

    email: Optional[EmailStr] = Field(default=None, description="User email address")
    name: Optional[str] = Field(
        default=None, min_length=1, max_length=255, description="User full name"
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=256,
        description="New password (optional)",
    )
    role: Optional[RoleEnum] = Field(default=None, description="User role")

    @model_validator(mode="after")
    def validate_password_strength(self) -> "UserUpdate":
        """Validate password strength if provided."""
        password = self.password
        if password:
            if not any(c.isupper() for c in password):
                raise ValueError("Password must contain at least one uppercase letter")
            if not any(c.islower() for c in password):
                raise ValueError("Password must contain at least one lowercase letter")
            if not any(c.isdigit() for c in password):
                raise ValueError("Password must contain at least one digit")
        return self


class UserResponse(BaseModel):
    """User response schema."""

    id: str = Field(description="User ID")
    email: EmailStr = Field(description="User email address")
    name: str = Field(description="User full name")
    role: RoleEnum = Field(description="User role")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


# ============================================================================
# Sensor Schemas
# ============================================================================


class SensorAgentCreate(BaseModel):
    """Sensor agent creation request."""

    name: str = Field(min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(
        default=None, max_length=1000, description="Agent description"
    )
    location: Optional[str] = Field(
        default=None, max_length=255, description="Agent location"
    )
    tags: Optional[list[str]] = Field(
        default=None, description="Agent tags for organization"
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate tags are non-empty strings."""
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Maximum 50 tags allowed")
        return [tag.strip() for tag in v if tag.strip()]


class SensorCheckCreate(BaseModel):
    """Sensor check creation request."""

    name: str = Field(min_length=1, max_length=255, description="Check name")
    check_type: CheckTypeEnum = Field(description="Type of check to perform")
    target: str = Field(
        min_length=1, max_length=1000, description="Check target (URL/IP/domain)"
    )
    interval: int = Field(
        ge=10, le=3600, description="Check interval in seconds (10-3600)"
    )
    timeout: int = Field(ge=1, le=60, description="Check timeout in seconds (1-60)")
    enabled: bool = Field(default=True, description="Enable or disable check")
    port: Optional[int] = Field(
        default=None, ge=1, le=65535, description="Port number (optional, for TCP)"
    )
    method: Optional[str] = Field(
        default=None,
        pattern="^(GET|POST|PUT|DELETE|HEAD|PATCH)$",
        description="HTTP method (for HTTP/HTTPS checks)",
    )
    expected_status: Optional[int] = Field(
        default=None,
        ge=100,
        le=599,
        description="Expected HTTP status code (for HTTP/HTTPS)",
    )
    headers: Optional[dict[str, str]] = Field(
        default=None, description="Custom HTTP headers"
    )

    @model_validator(mode="after")
    def validate_check_config(self) -> "SensorCheckCreate":
        """Validate check configuration based on type."""
        if self.check_type in (CheckTypeEnum.HTTP, CheckTypeEnum.HTTPS):
            if not self.method:
                raise ValueError(
                    f"{self.check_type.value} check requires 'method' field"
                )
        if self.check_type == CheckTypeEnum.TCP:
            if not self.port:
                raise ValueError("TCP check requires 'port' field")
        return self


class SensorResultSubmit(BaseModel):
    """Sensor check result submission."""

    check_id: str = Field(description="Check ID")
    status: str = Field(
        pattern="^(success|failure|timeout)$", description="Check status"
    )
    response_time: float = Field(ge=0, description="Response time in milliseconds")
    status_code: Optional[int] = Field(
        default=None, ge=0, le=599, description="HTTP status code (if applicable)"
    )
    message: Optional[str] = Field(
        default=None, max_length=1000, description="Status message or error details"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""

        from_attributes = True
