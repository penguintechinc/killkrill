"""
KillKrill API - Users Blueprint
User management endpoints
"""

from datetime import datetime

from quart import Blueprint, request, jsonify, g
import structlog

from middleware.auth import require_auth, require_role, hash_password
from models.database import get_db

logger = structlog.get_logger(__name__)

users_bp = Blueprint('users', __name__)


@users_bp.route('/', methods=['GET'])
@require_auth()
@require_role(['admin'])
async def list_users():
    """List all users (admin only)"""
    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    users = db(db.users).select(orderby=~db.users.created_at)

    return jsonify({
        'users': [{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
        } for user in users],
        'total': len(users)
    })


@users_bp.route('/<int:user_id>', methods=['GET'])
@require_auth()
async def get_user(user_id: int):
    """Get user by ID"""
    # Users can only view their own profile unless admin
    if g.auth.get('role') != 'admin' and g.auth.get('user_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403

    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    user = db(db.users.id == user_id).select().first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'last_login': user.last_login.isoformat() if user.last_login else None,
    })


@users_bp.route('/', methods=['POST'])
@require_auth()
@require_role(['admin'])
async def create_user():
    """Create a new user (admin only)"""
    data = await request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required = ['username', 'email', 'password']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    # Check for existing user
    existing = db(
        (db.users.username == data.get('username')) |
        (db.users.email == data.get('email'))
    ).select().first()

    if existing:
        return jsonify({'error': 'Username or email already exists'}), 409

    user_id = db.users.insert(
        username=data.get('username'),
        email=data.get('email'),
        password_hash=hash_password(data.get('password')),
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        role=data.get('role', 'user'),
        is_active=data.get('is_active', True),
    )
    db.commit()

    logger.info("user_created", user_id=user_id, by=g.auth.get('user_id'))

    return jsonify({'id': user_id, 'message': 'User created'}), 201


@users_bp.route('/<int:user_id>', methods=['PUT'])
@require_auth()
async def update_user(user_id: int):
    """Update user profile"""
    # Users can only update their own profile unless admin
    if g.auth.get('role') != 'admin' and g.auth.get('user_id') != user_id:
        return jsonify({'error': 'Access denied'}), 403

    data = await request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    user = db(db.users.id == user_id).select().first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Build update dict
    update_fields = {}

    # Fields users can update themselves
    for field in ['first_name', 'last_name']:
        if field in data:
            update_fields[field] = data[field]

    # Admin-only fields
    if g.auth.get('role') == 'admin':
        for field in ['username', 'email', 'role', 'is_active']:
            if field in data:
                update_fields[field] = data[field]

    # Password update
    if data.get('password'):
        update_fields['password_hash'] = hash_password(data['password'])

    if update_fields:
        user.update_record(**update_fields)
        db.commit()
        logger.info("user_updated", user_id=user_id, by=g.auth.get('user_id'))

    return jsonify({'message': 'User updated'})


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@require_auth()
@require_role(['admin'])
async def delete_user(user_id: int):
    """Delete/deactivate user (admin only)"""
    # Prevent self-deletion
    if g.auth.get('user_id') == user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    db = await get_db()
    if not db:
        return jsonify({'error': 'Database unavailable'}), 503

    user = db(db.users.id == user_id).select().first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Soft delete - deactivate instead of removing
    user.update_record(is_active=False)
    db.commit()

    logger.info("user_deleted", user_id=user_id, by=g.auth.get('user_id'))

    return jsonify({'message': 'User deactivated'})
