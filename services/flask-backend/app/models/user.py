"""
KillKrill Flask Backend - User and Role Models

Flask-SQLAlchemy models for authentication with Flask-Security-Too.
"""

from datetime import datetime
from typing import List
from flask_security import UserMixin, RoleMixin
from .database import db

# Association table for many-to-many relationship
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)


class Role(db.Model, RoleMixin):
    """Role model for RBAC"""
    __tablename__ = 'role'

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON(), default=list)
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Role {self.name}>'


class User(db.Model, UserMixin):
    """User model for authentication"""
    __tablename__ = 'user'

    id = db.Column(db.Integer(), primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    active = db.Column(db.Boolean(), default=True, nullable=False)
    fs_uniquifier = db.Column(db.String(255), unique=True, nullable=False)
    confirmed_at = db.Column(db.DateTime())
    created_at = db.Column(db.DateTime(), default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime())
    last_login_ip = db.Column(db.String(45))

    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))

    def __repr__(self):
        return f'<User {self.username}>'

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role"""
        return any(role.name == role_name for role in self.roles)

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        for role in self.roles:
            if role.permissions and permission in role.permissions:
                return True
        return False

    def get_permissions(self) -> List[str]:
        """Get all permissions for user"""
        permissions = set()
        for role in self.roles:
            if role.permissions:
                permissions.update(role.permissions)
        return list(permissions)

    def get_roles(self) -> List[str]:
        """Get all role names for user"""
        return [role.name for role in self.roles]


__all__ = ['User', 'Role', 'roles_users']
