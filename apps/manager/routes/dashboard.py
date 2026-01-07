"""
Dashboard routes (/, /index.html)
"""
from quart import Blueprint, render_template_string
import os
import socket
import psutil

bp = Blueprint('dashboard', __name__)


def check_service_status():
    """Check status of all KillKrill services"""
    services = {
        'postgres': {'port': 5432, 'type': 'database'},
        'redis': {'port': 6379, 'type': 'cache'},
        'elasticsearch': {'port': 9200, 'type': 'search'},
        'kibana': {'port': 5601, 'type': 'visualization'},
        'logstash': {'port': 9600, 'type': 'processing'},
        'prometheus': {'port': 9090, 'type': 'monitoring'},
        'grafana': {'port': 3000, 'type': 'visualization'},
        'alertmanager': {'port': 9093, 'type': 'alerting'},
        'fleet-server': {'port': 8084, 'type': 'device_management'},
        'fleet-mysql': {'port': 3307, 'type': 'database'},
        'log-receiver': {'port': 8081, 'type': 'receiver'},
        'metrics-receiver': {'port': 8082, 'type': 'receiver'}
    }

    status = {}
    for service, config in services.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', config['port']))
            sock.close()
            status[service] = {
                'status': 'healthy' if result == 0 else 'down',
                'port': config['port'],
                'type': config['type']
            }
        except:
            status[service] = {
                'status': 'error',
                'port': config['port'],
                'type': config['type']
            }

    return status


def get_system_metrics():
    """Get real system metrics"""
    try:
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'uptime': psutil.boot_time()
        }
    except:
        return {
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_percent': 0,
            'uptime': 0
        }


def generate_service_cards(services):
    """Generate HTML for service status cards"""
    cards_html = ""
    for service, info in services.items():
        status_class = f"status-{info['status']}"
        service_display = service.replace('-', ' ').replace('_', ' ').title()

        cards_html += f"""
        <div class="service-card">
            <div class="service-status {status_class}"></div>
            <div class="service-name">{service_display}</div>
            <div class="service-type">{info['type']}</div>
            <div class="service-port">:{info['port']}</div>
        </div>
        """
    return cards_html


@bp.route('/', methods=['GET'])
@bp.route('/index.html', methods=['GET'])
async def index():
    """KillKrill Management Portal Dashboard"""
    from quart import current_app

    license_key = current_app.config.get('LICENSE_KEY', 'PENG-DEMO-DEMO-DEMO-DEMO-DEMO')

    # Determine license tier
    if 'DEMO' in license_key:
        license_tier = 'Demo'
    elif license_key.startswith('PENG-'):
        license_tier = 'Enterprise'
    else:
        license_tier = 'Community'

    # Get real service status and system metrics
    services = check_service_status()
    metrics = get_system_metrics()

    # Read the dashboard template
    with open('/home/penguin/code/killkrill/apps/manager/templates/dashboard.html', 'r') as f:
        template = f.read()

    return await render_template_string(
        template,
        license_tier=license_tier,
        license_key=license_key,
        service_cards=generate_service_cards(services),
        cpu_percent=metrics['cpu_percent'],
        memory_percent=metrics['memory_percent'],
        disk_percent=metrics['disk_percent']
    )
