"""
PyDAL table definitions for Killkrill.

All tables are defined here with migrate=True for automatic schema management.
"""

from datetime import datetime

from pydal import DAL, Field


def define_all_tables(db: DAL) -> None:
    """
    Define all Killkrill tables with PyDAL.

    Args:
        db: PyDAL instance
    """
    _define_auth_tables(db)
    _define_receiver_tables(db)
    _define_metrics_tables(db)
    _define_log_tables(db)
    _define_alert_tables(db)


def _define_auth_tables(db: DAL) -> None:
    """Define authentication and authorization tables."""

    # Roles table
    db.define_table(
        "auth_role",
        Field("name", "string", length=80, unique=True, notnull=True),
        Field("description", "text"),
        Field("permissions", "json"),  # JSON array of permission strings
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", update=datetime.utcnow),
        migrate=True,
        format="%(name)s",
    )

    # Users table
    db.define_table(
        "auth_user",
        Field("email", "string", length=255, unique=True, notnull=True),
        Field("password", "password", notnull=True),  # Hashed password
        Field("first_name", "string", length=128),
        Field("last_name", "string", length=128),
        Field("active", "boolean", default=True),
        Field("confirmed_at", "datetime"),
        Field("fs_uniquifier", "string", length=255, unique=True),  # Flask-Security
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", update=datetime.utcnow),
        Field("last_login_at", "datetime"),
        Field("current_login_at", "datetime"),
        Field("last_login_ip", "string", length=100),
        Field("current_login_ip", "string", length=100),
        Field("login_count", "integer", default=0),
        migrate=True,
        format="%(email)s",
    )

    # User-Role mapping (many-to-many)
    db.define_table(
        "auth_user_role",
        Field("user_id", "reference auth_user", notnull=True, ondelete="CASCADE"),
        Field("role_id", "reference auth_role", notnull=True, ondelete="CASCADE"),
        Field("created_at", "datetime", default=datetime.utcnow),
        migrate=True,
    )

    # API Keys table
    db.define_table(
        "api_key",
        Field("user_id", "reference auth_user", notnull=True, ondelete="CASCADE"),
        Field("name", "string", length=128, notnull=True),
        Field("key_hash", "string", length=255, notnull=True),  # SHA256 hash
        Field("key_prefix", "string", length=16),  # First 8 chars for identification
        Field("active", "boolean", default=True),
        Field("expires_at", "datetime"),
        Field("scopes", "json"),  # JSON array of allowed scopes
        Field("last_used_at", "datetime"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", update=datetime.utcnow),
        migrate=True,
    )

    # Sessions table (for token management)
    db.define_table(
        "auth_session",
        Field("user_id", "reference auth_user", notnull=True, ondelete="CASCADE"),
        Field("token_hash", "string", length=255, notnull=True),
        Field("user_agent", "text"),
        Field("ip_address", "string", length=100),
        Field("expires_at", "datetime", notnull=True),
        Field("created_at", "datetime", default=datetime.utcnow),
        migrate=True,
    )


def _define_receiver_tables(db: DAL) -> None:
    """Define tables for receiver service configuration."""

    # Receiver instances
    db.define_table(
        "receiver",
        Field("name", "string", length=128, unique=True, notnull=True),
        Field("type", "string", length=32, notnull=True),  # syslog, http, prometheus
        Field("protocol", "string", length=16),  # tcp, udp, http
        Field("port", "integer"),
        Field("enabled", "boolean", default=True),
        Field("config", "json"),  # Receiver-specific configuration
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", update=datetime.utcnow),
        migrate=True,
    )

    # Receiver metrics
    db.define_table(
        "receiver_metrics",
        Field("receiver_id", "reference receiver", notnull=True, ondelete="CASCADE"),
        Field("timestamp", "datetime", default=datetime.utcnow),
        Field("messages_received", "bigint", default=0),
        Field("bytes_received", "bigint", default=0),
        Field("errors", "integer", default=0),
        migrate=True,
    )


def _define_metrics_tables(db: DAL) -> None:
    """Define tables for metrics storage and aggregation."""

    # Raw metrics (time-series)
    db.define_table(
        "metric",
        Field("name", "string", length=255, notnull=True),
        Field("value", "double", notnull=True),
        Field("timestamp", "datetime", default=datetime.utcnow, notnull=True),
        Field("labels", "json"),  # Key-value pairs
        Field("source", "string", length=128),
        Field("metric_type", "string", length=32),  # counter, gauge, histogram
        migrate=True,
    )

    # Aggregated metrics (rolled up)
    db.define_table(
        "metric_aggregate",
        Field("name", "string", length=255, notnull=True),
        Field("interval", "string", length=16, notnull=True),  # 1m, 5m, 1h, 1d
        Field("timestamp", "datetime", notnull=True),
        Field("count", "bigint", default=0),
        Field("sum", "double", default=0.0),
        Field("min", "double"),
        Field("max", "double"),
        Field("avg", "double"),
        Field("labels", "json"),
        migrate=True,
    )


def _define_log_tables(db: DAL) -> None:
    """Define tables for log storage and indexing."""

    # Log entries
    db.define_table(
        "log_entry",
        Field("timestamp", "datetime", default=datetime.utcnow, notnull=True),
        Field("level", "string", length=16, notnull=True),  # debug, info, warn, error
        Field("message", "text", notnull=True),
        Field("source", "string", length=255),
        Field("hostname", "string", length=255),
        Field("application", "string", length=128),
        Field("facility", "string", length=32),
        Field("severity", "integer"),
        Field("tags", "json"),  # Array of tags
        Field("metadata", "json"),  # Additional structured data
        Field("raw_message", "text"),
        migrate=True,
    )

    # Log parsing rules
    db.define_table(
        "log_parser",
        Field("name", "string", length=128, unique=True, notnull=True),
        Field("pattern", "text", notnull=True),  # Regex pattern
        Field("field_mappings", "json"),  # Field extraction rules
        Field("enabled", "boolean", default=True),
        Field("priority", "integer", default=100),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", update=datetime.utcnow),
        migrate=True,
    )


def _define_alert_tables(db: DAL) -> None:
    """Define tables for alerting and notifications."""

    # Alert rules
    db.define_table(
        "alert_rule",
        Field("name", "string", length=128, unique=True, notnull=True),
        Field("description", "text"),
        Field("type", "string", length=32, notnull=True),  # metric, log, threshold
        Field("condition", "json", notnull=True),  # Alert condition definition
        Field(
            "severity", "string", length=16, default="warning"
        ),  # info, warning, critical
        Field("enabled", "boolean", default=True),
        Field("notification_channels", "json"),  # Array of channel IDs
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", update=datetime.utcnow),
        migrate=True,
    )

    # Alert history
    db.define_table(
        "alert_history",
        Field("alert_rule_id", "reference alert_rule", ondelete="CASCADE"),
        Field("triggered_at", "datetime", default=datetime.utcnow, notnull=True),
        Field("resolved_at", "datetime"),
        Field("status", "string", length=16, default="firing"),  # firing, resolved
        Field("value", "double"),
        Field("message", "text"),
        Field("metadata", "json"),
        migrate=True,
    )

    # Notification channels
    db.define_table(
        "notification_channel",
        Field("name", "string", length=128, unique=True, notnull=True),
        Field("type", "string", length=32, notnull=True),  # email, slack, pagerduty
        Field("config", "json", notnull=True),  # Channel-specific config
        Field("enabled", "boolean", default=True),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", update=datetime.utcnow),
        migrate=True,
    )
