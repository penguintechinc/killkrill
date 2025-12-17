"""
KillKrill Flask Backend - Audit Log Model

Flask-SQLAlchemy model for audit logging.
"""

from datetime import datetime
from .database import db


class AuditLog(db.Model):
    """Audit log model for tracking user actions"""
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id'))
    action = db.Column(db.String(255), nullable=False, index=True)
    resource_type = db.Column(db.String(255), nullable=False)
    resource_id = db.Column(db.String(255), index=True)
    details = db.Column(db.JSON())
    status = db.Column(db.String(50), default='success')
    error_message = db.Column(db.Text())
    client_ip = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    correlation_id = db.Column(db.String(255), index=True)
    created_at = db.Column(db.DateTime(), default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<AuditLog {self.action}>'


__all__ = ['AuditLog']
