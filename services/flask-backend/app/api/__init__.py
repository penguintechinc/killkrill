"""
KillKrill Flask Backend - API Package

Contains API blueprints and endpoint definitions.
"""

from .v1 import api_v1_bp

__all__ = [
    'api_v1_bp',
]
