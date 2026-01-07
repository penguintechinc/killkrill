"""
KillKrill Log Receiver - Route Blueprints
"""

from .health import health_bp
from .index import index_bp
from .ingest import ingest_bp
from .metrics import metrics_bp

__all__ = ["health_bp", "metrics_bp", "ingest_bp", "index_bp"]
