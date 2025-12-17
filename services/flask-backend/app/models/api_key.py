"""
KillKrill Flask Backend - API Key Model

Flask-SQLAlchemy model for API key management.
"""

from datetime import datetime
from .database import db


class APIKey(db.Model):
    """API Key model for authentication"""
    __tablename__ = 'api_key'

    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id'), nullable=False)
    key_hash = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean(), default=True, nullable=False)
    expires_at = db.Column(db.DateTime())
    last_used_at = db.Column(db.DateTime())
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('api_keys', lazy='dynamic'))

    def __repr__(self):
        return f'<APIKey {self.name}>'

    def is_expired(self) -> bool:
        """Check if API key has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if API key is valid (active and not expired)"""
        return self.is_active and not self.is_expired()


__all__ = ['APIKey']
