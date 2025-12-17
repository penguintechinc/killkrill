"""API v1 blueprint registration module.

Registers all API v1 blueprints with lazy loading to avoid circular imports.
"""

from flask import Blueprint

# Create main API v1 blueprint
api_v1_bp = Blueprint('api_v1', __name__)


def register_blueprints(app):
    """Register all API v1 blueprints with the Flask application."""
    # Lazy imports to avoid circular dependencies
    from .auth import auth_bp
    from .users import users_bp
    from .sensors import sensors_bp
    from .dashboard import dashboard_bp
    from .fleet import fleet_bp
    from .infrastructure import infrastructure_bp
    from .ai_analysis import ai_analysis_bp
    from .licensing import licensing_bp

    blueprints = [
        (auth_bp, '/auth'),
        (users_bp, '/users'),
        (sensors_bp, '/sensors'),
        (dashboard_bp, '/dashboard'),
        (fleet_bp, '/fleet'),
        (infrastructure_bp, '/infrastructure'),
        (ai_analysis_bp, '/ai'),
        (licensing_bp, '/licensing'),
    ]

    for blueprint, url_prefix in blueprints:
        api_v1_bp.register_blueprint(blueprint, url_prefix=url_prefix)

    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')


__all__ = ['api_v1_bp', 'register_blueprints']
