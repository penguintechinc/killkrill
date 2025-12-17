"""
KillKrill Flask Backend - gRPC Package

Contains gRPC service definitions and handlers.
gRPC server runs on separate port (default: 50051) independent of Flask HTTP server.

Services included:
- DashboardService: System metrics and statistics
- SensorService: Sensor data management
- UserService: User management operations
- AuthService: Token validation and authentication
"""

from .server import (
    DashboardServicer,
    SensorServicer,
    UserServicer,
    AuthServicer,
    create_grpc_server,
    serve
)

__all__ = [
    'DashboardServicer',
    'SensorServicer',
    'UserServicer',
    'AuthServicer',
    'create_grpc_server',
    'serve',
]

__version__ = '1.0.0'
