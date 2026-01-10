"""
KillKrill Log Receiver - Configuration
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Base configuration"""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://killkrill:killkrill123@postgresql:5432/killkrill"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")
    RECEIVER_PORT: int = int(os.getenv("RECEIVER_PORT", "8081"))
    API_URL: str = os.getenv("API_URL", "http://flask-backend:5000")
    GRPC_URL: str = os.getenv("GRPC_URL", "flask-backend:50051")
    CLIENT_ID: str = os.getenv("RECEIVER_CLIENT_ID", "log-receiver")
    CLIENT_SECRET: str = os.getenv("RECEIVER_CLIENT_SECRET", "")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    @property
    def pydal_database_url(self) -> str:
        """Convert PostgreSQL URL to PyDAL format"""
        return self.DATABASE_URL.replace("postgresql://", "postgres://")


def get_config() -> Config:
    """Get application configuration"""
    return Config()
