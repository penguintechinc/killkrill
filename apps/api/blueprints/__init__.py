"""
KillKrill API - Blueprints
API endpoint blueprints
"""

from .ai_analysis import ai_analysis_bp
from .auth import auth_bp
from .dashboard import dashboard_bp
from .fleet import fleet_bp
from .infrastructure import infrastructure_bp
from .licensing import licensing_bp
from .sensors import sensors_bp
from .users import users_bp
from .websocket import websocket_bp

__all__ = [
    "auth_bp",
    "dashboard_bp",
    "users_bp",
    "sensors_bp",
    "infrastructure_bp",
    "fleet_bp",
    "ai_analysis_bp",
    "licensing_bp",
    "websocket_bp",
]
