"""
Infrastructure configuration routes (/databases, /infrastructure, /monitoring, /security)
"""
from quart import Blueprint, render_template_string

bp = Blueprint('infrastructure', __name__)


@bp.route('/databases', methods=['GET'])
async def databases():
    """Database configuration management page"""
    with open('/home/penguin/code/killkrill/apps/manager/templates/databases.html', 'r') as f:
        template = f.read()
    return await render_template_string(template)


@bp.route('/infrastructure', methods=['GET'])
async def infrastructure():
    """Infrastructure configuration management page"""
    with open('/home/penguin/code/killkrill/apps/manager/templates/infrastructure.html', 'r') as f:
        template = f.read()
    return await render_template_string(template)


@bp.route('/monitoring', methods=['GET'])
async def monitoring():
    """Monitoring configuration management page"""
    with open('/home/penguin/code/killkrill/apps/manager/templates/monitoring.html', 'r') as f:
        template = f.read()
    return await render_template_string(template)


@bp.route('/security', methods=['GET'])
async def security():
    """Security and networking configuration page"""
    with open('/home/penguin/code/killkrill/apps/manager/templates/security.html', 'r') as f:
        template = f.read()
    return await render_template_string(template)


@bp.route('/fleet-config', methods=['GET'])
async def fleet_config():
    """Fleet management configuration page"""
    with open('/home/penguin/code/killkrill/apps/manager/templates/fleet_config.html', 'r') as f:
        template = f.read()
    return await render_template_string(template)


@bp.route('/logs', methods=['GET'])
async def logs():
    """System logs viewer"""
    with open('/home/penguin/code/killkrill/apps/manager/templates/logs.html', 'r') as f:
        template = f.read()
    return await render_template_string(template)
