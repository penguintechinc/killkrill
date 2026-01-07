"""Configuration for metrics-receiver service."""

import os


class Config:
    """Base configuration."""

    # Database
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", "postgresql://killkrill:killkrill123@postgres:5432/killkrill"
    )

    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")

    # ReceiverClient
    API_URL = os.environ.get("API_URL", "http://flask-backend:5000")
    GRPC_URL = os.environ.get("GRPC_URL", "flask-backend:50051")
    RECEIVER_CLIENT_ID = os.environ.get("RECEIVER_CLIENT_ID", "")
    RECEIVER_CLIENT_SECRET = os.environ.get("RECEIVER_CLIENT_SECRET", "")

    @property
    def pydal_database_url(self) -> str:
        """Convert PostgreSQL URL to PyDAL format."""
        return self.DATABASE_URL.replace("postgresql://", "postgres://")
