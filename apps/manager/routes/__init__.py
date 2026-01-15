"""
Manager service routes
"""

from .dashboard import bp as dashboard_bp
from .embeds import bp as embeds_bp
from .health import bp as health_bp
from .infrastructure import bp as infrastructure_bp
from .services import bp as services_bp

__all__ = ["health_bp", "dashboard_bp", "infrastructure_bp", "services_bp", "embeds_bp"]
