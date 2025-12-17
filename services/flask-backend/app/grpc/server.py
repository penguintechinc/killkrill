"""
KillKrill gRPC Server

Provides gRPC service implementations for internal communication between services.
Handles dashboard statistics, sensor management, user operations, and authentication.
Runs asynchronously on port 50051.
"""

import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

import grpc
from grpc import aio
import structlog

# This will be populated with generated protobuf code
# For now, we create stub implementations
logger = structlog.get_logger()


@dataclass
class DashboardStats:
    """Dashboard statistics dataclass"""
    total_sensors: int = 0
    active_sensors: int = 0
    inactive_sensors: int = 0
    total_users: int = 0
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    disk_usage_bytes: int = 0
    last_updated: str = ""
    timestamp: str = ""


@dataclass
class SensorData:
    """Sensor data dataclass"""
    id: str = ""
    name: str = ""
    sensor_type: str = ""
    status: str = "inactive"
    current_value: float = 0.0
    unit: str = ""
    location: str = ""
    last_reading_time: str = ""
    metadata: Dict[str, str] = None


@dataclass
class UserInfo:
    """User information dataclass"""
    id: str = ""
    username: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    active: bool = True
    roles: List[str] = None
    permissions: List[str] = None
    created_at: str = ""
    updated_at: str = ""
    last_login_at: str = ""


class DashboardServicer:
    """gRPC Dashboard Service Implementation"""

    def __init__(self, flask_app=None):
        """Initialize with Flask app reference"""
        self.flask_app = flask_app
        self.logger = structlog.get_logger()

    async def GetStats(self, request, context):
        """Get dashboard statistics"""
        try:
            self.logger.info(
                'dashboard_stats_requested',
                user_id=request.user_id,
                correlation_id=request.correlation_id
            )

            stats = DashboardStats(
                total_sensors=42,
                active_sensors=38,
                inactive_sensors=4,
                total_users=15,
                cpu_usage_percent=45.3,
                memory_usage_percent=62.1,
                disk_usage_bytes=5368709120,
                last_updated=datetime.utcnow().isoformat(),
                timestamp=datetime.utcnow().isoformat()
            )

            return {
                'total_sensors': stats.total_sensors,
                'active_sensors': stats.active_sensors,
                'inactive_sensors': stats.inactive_sensors,
                'total_users': stats.total_users,
                'cpu_usage_percent': stats.cpu_usage_percent,
                'memory_usage_percent': stats.memory_usage_percent,
                'disk_usage_bytes': stats.disk_usage_bytes,
                'last_updated': stats.last_updated,
                'timestamp': stats.timestamp
            }
        except Exception as e:
            self.logger.error('dashboard_stats_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def GetSystemHealth(self, request, context):
        """Get system health status"""
        try:
            self.logger.info(
                'system_health_requested',
                correlation_id=request.correlation_id
            )

            health = {
                'status': 'healthy',
                'service_name': 'killkrill-flask-backend',
                'version': os.getenv('APP_VERSION', '1.0.0'),
                'uptime_seconds': 86400,
                'components': [
                    {'name': 'database', 'status': 'healthy', 'message': 'PostgreSQL connected'},
                    {'name': 'cache', 'status': 'healthy', 'message': 'Redis connected'},
                    {'name': 'api', 'status': 'healthy', 'message': 'REST API operational'}
                ],
                'timestamp': datetime.utcnow().isoformat()
            }

            return health
        except Exception as e:
            self.logger.error('system_health_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def GetMetrics(self, request, context):
        """Get system metrics"""
        try:
            self.logger.info(
                'metrics_requested',
                metric_type=request.metric_type,
                correlation_id=request.correlation_id
            )

            metrics = {
                'metric_type': request.metric_type,
                'data_points': [
                    {'timestamp': datetime.utcnow().isoformat(), 'value': 45.3},
                    {'timestamp': datetime.utcnow().isoformat(), 'value': 48.1}
                ],
                'timestamp': datetime.utcnow().isoformat()
            }

            return metrics
        except Exception as e:
            self.logger.error('metrics_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))


class SensorServicer:
    """gRPC Sensor Service Implementation"""

    def __init__(self, flask_app=None):
        """Initialize with Flask app reference"""
        self.flask_app = flask_app
        self.logger = structlog.get_logger()

    async def GetSensorData(self, request, context):
        """Get sensor data by ID"""
        try:
            self.logger.info(
                'sensor_data_requested',
                sensor_id=request.sensor_id,
                user_id=request.user_id,
                correlation_id=request.correlation_id
            )

            sensor = SensorData(
                id=request.sensor_id,
                name=f"Sensor {request.sensor_id}",
                sensor_type="temperature",
                status="active",
                current_value=23.5,
                unit="celsius",
                location="Room A",
                last_reading_time=datetime.utcnow().isoformat(),
                metadata={}
            )

            return {
                'sensor': {
                    'id': sensor.id,
                    'name': sensor.name,
                    'sensor_type': sensor.sensor_type,
                    'status': sensor.status,
                    'current_value': sensor.current_value,
                    'unit': sensor.unit,
                    'location': sensor.location,
                    'last_reading_time': sensor.last_reading_time,
                    'metadata': sensor.metadata
                },
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error('sensor_data_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def ListSensors(self, request, context):
        """List all sensors for user"""
        try:
            self.logger.info(
                'sensors_list_requested',
                user_id=request.user_id,
                limit=request.limit,
                offset=request.offset,
                correlation_id=request.correlation_id
            )

            sensors = []
            for i in range(request.limit):
                sensor = SensorData(
                    id=f"sensor_{request.offset + i}",
                    name=f"Sensor {request.offset + i}",
                    sensor_type="temperature",
                    status="active" if i % 2 == 0 else "inactive",
                    current_value=20.0 + i,
                    unit="celsius",
                    location=f"Location {i}",
                    last_reading_time=datetime.utcnow().isoformat()
                )
                sensors.append({
                    'id': sensor.id,
                    'name': sensor.name,
                    'sensor_type': sensor.sensor_type,
                    'status': sensor.status,
                    'current_value': sensor.current_value,
                    'unit': sensor.unit,
                    'location': sensor.location,
                    'last_reading_time': sensor.last_reading_time,
                    'metadata': {}
                })

            return {
                'sensors': sensors,
                'total_count': 42,
                'limit': request.limit,
                'offset': request.offset,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error('sensors_list_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def UpdateSensor(self, request, context):
        """Update sensor information"""
        try:
            self.logger.info(
                'sensor_update_requested',
                sensor_id=request.sensor_id,
                user_id=request.user_id,
                correlation_id=request.correlation_id
            )

            sensor = SensorData(
                id=request.sensor_id,
                name=request.name or f"Sensor {request.sensor_id}",
                sensor_type="temperature",
                status=request.status or "active",
                current_value=23.5,
                unit="celsius",
                location="Room A",
                last_reading_time=datetime.utcnow().isoformat(),
                metadata=dict(request.metadata) if request.metadata else {}
            )

            return {
                'id': sensor.id,
                'name': sensor.name,
                'sensor_type': sensor.sensor_type,
                'status': sensor.status,
                'current_value': sensor.current_value,
                'unit': sensor.unit,
                'location': sensor.location,
                'last_reading_time': sensor.last_reading_time,
                'metadata': sensor.metadata
            }
        except Exception as e:
            self.logger.error('sensor_update_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))


class UserServicer:
    """gRPC User Service Implementation"""

    def __init__(self, flask_app=None):
        """Initialize with Flask app reference"""
        self.flask_app = flask_app
        self.logger = structlog.get_logger()

    async def GetUser(self, request, context):
        """Get user by ID"""
        try:
            self.logger.info(
                'user_requested',
                user_id=request.user_id,
                correlation_id=request.correlation_id
            )

            user = UserInfo(
                id=request.user_id,
                username="testuser",
                email="test@example.com",
                first_name="Test",
                last_name="User",
                active=True,
                roles=["viewer", "analyst"],
                permissions=["read", "write"],
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                last_login_at=datetime.utcnow().isoformat()
            )

            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'active': user.active,
                'roles': user.roles or [],
                'permissions': user.permissions or [],
                'created_at': user.created_at,
                'updated_at': user.updated_at,
                'last_login_at': user.last_login_at,
                'metadata': {}
            }
        except Exception as e:
            self.logger.error('user_get_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def ListUsers(self, request, context):
        """List users"""
        try:
            self.logger.info(
                'users_list_requested',
                limit=request.limit,
                offset=request.offset,
                active_only=request.active_only,
                correlation_id=request.correlation_id
            )

            users = []
            for i in range(request.limit):
                user = UserInfo(
                    id=f"user_{request.offset + i}",
                    username=f"user{request.offset + i}",
                    email=f"user{request.offset + i}@example.com",
                    first_name=f"User{request.offset + i}",
                    last_name="Test",
                    active=True,
                    roles=["viewer"],
                    permissions=["read"],
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat()
                )
                users.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'active': user.active,
                    'roles': user.roles or [],
                    'permissions': user.permissions or [],
                    'created_at': user.created_at,
                    'updated_at': user.updated_at,
                    'metadata': {}
                })

            return {
                'users': users,
                'total_count': 42,
                'limit': request.limit,
                'offset': request.offset,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error('users_list_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def UpdateUser(self, request, context):
        """Update user"""
        try:
            self.logger.info(
                'user_update_requested',
                user_id=request.user_id,
                correlation_id=request.correlation_id
            )

            user = UserInfo(
                id=request.user_id,
                username="testuser",
                email="test@example.com",
                first_name=request.first_name or "Test",
                last_name=request.last_name or "User",
                active=request.active if request.active else True,
                roles=list(request.roles) if request.roles else ["viewer"],
                permissions=["read"],
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )

            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'active': user.active,
                'roles': user.roles or [],
                'permissions': user.permissions or [],
                'created_at': user.created_at,
                'updated_at': user.updated_at,
                'metadata': {}
            }
        except Exception as e:
            self.logger.error('user_update_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def DeleteUser(self, request, context):
        """Delete user"""
        try:
            self.logger.info(
                'user_delete_requested',
                user_id=request.user_id,
                correlation_id=request.correlation_id
            )

            return {
                'success': True,
                'message': f'User {request.user_id} deleted successfully',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error('user_delete_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))


class AuthServicer:
    """gRPC Authentication Service Implementation"""

    def __init__(self, flask_app=None):
        """Initialize with Flask app reference"""
        self.flask_app = flask_app
        self.logger = structlog.get_logger()

    async def ValidateToken(self, request, context):
        """Validate JWT token"""
        try:
            self.logger.info(
                'token_validation_requested',
                correlation_id=request.correlation_id
            )

            return {
                'valid': True,
                'user_id': 'user_123',
                'roles': ['viewer', 'analyst'],
                'permissions': ['read', 'write'],
                'expires_in_seconds': 86400,
                'message': 'Token is valid',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error('token_validation_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def RefreshToken(self, request, context):
        """Refresh JWT token"""
        try:
            self.logger.info(
                'token_refresh_requested',
                correlation_id=request.correlation_id
            )

            return {
                'access_token': 'new_jwt_token_here',
                'token_type': 'Bearer',
                'expires_in': 86400,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error('token_refresh_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def GetAuthInfo(self, request, context):
        """Get authentication information"""
        try:
            self.logger.info(
                'auth_info_requested',
                user_id=request.user_id,
                correlation_id=request.correlation_id
            )

            return {
                'user_id': request.user_id,
                'username': 'testuser',
                'roles': ['viewer', 'analyst'],
                'permissions': ['read', 'write'],
                'authenticated_at': datetime.utcnow().isoformat(),
                'token_expires_at': datetime.utcnow().isoformat(),
                'claims': {'sub': request.user_id, 'iat': '1234567890'},
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error('auth_info_error', error=str(e))
            await context.abort(grpc.StatusCode.INTERNAL, str(e))


async def serve(flask_app=None, port: int = 50051):
    """Start gRPC server"""
    server = aio.server()

    # Create service instances
    dashboard_servicer = DashboardServicer(flask_app)
    sensor_servicer = SensorServicer(flask_app)
    user_servicer = UserServicer(flask_app)
    auth_servicer = AuthServicer(flask_app)

    # Add services to server (when proto stubs are generated)
    # For now, we just start the server with registered servicers

    server.add_insecure_port(f'[::]:{port}')

    logger.info('grpc_server_starting', port=port)

    await server.start()
    logger.info('grpc_server_started', port=port, service='killkrill')

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info('grpc_server_stopping')
        await server.stop(grace=5)


def create_grpc_server(flask_app=None, port: int = 50051):
    """Create and return gRPC server configuration"""
    return {
        'servicers': {
            'dashboard': DashboardServicer(flask_app),
            'sensor': SensorServicer(flask_app),
            'user': UserServicer(flask_app),
            'auth': AuthServicer(flask_app)
        },
        'port': port,
        'serve_function': serve
    }


if __name__ == '__main__':
    asyncio.run(serve(port=50051))
