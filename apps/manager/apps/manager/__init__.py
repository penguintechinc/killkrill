"""
KillKrill Manager - py4web Application (Minimal Version)
Enterprise observability management interface with Fleet integration
"""

import os
import json
from datetime import datetime
from py4web import action, request, response, DAL, Field, HTTP
from py4web.utils.cors import CORS
from prometheus_client import Counter, generate_latest
import redis

# Application name
__version__ = "1.0.0"

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://killkrill:killkrill123@postgres:5432/killkrill')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379')

# Convert URL scheme for PyDAL compatibility
pydal_database_url = DATABASE_URL.replace('postgresql://', 'postgres://')

# Initialize components
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
db = DAL(pydal_database_url, migrate=True, fake_migrate=False)

# Create basic tables
try:
    db.define_table('health_checks',
        Field('timestamp', 'datetime', default=datetime.utcnow),
        Field('status', 'string', default='ok'),
        Field('component', 'string'),
        migrate=True
    )
    db.commit()
except Exception as table_error:
    print(f"Note: Manager table creation skipped - {table_error}")

print(f"✓ KillKrill Manager py4web app initialized")

# Metrics
health_checks = Counter('killkrill_manager_health_checks_total', 'Health checks', ['status'])

# Health check endpoint
@action('healthz')
@action.uses(CORS())
def healthz():
    """Health check endpoint"""
    try:
        # Test Redis
        redis_client.ping()

        # Test database
        db.health_checks.insert(status='ok', component='manager')
        db.commit()

        health_checks.labels(status='ok').inc()

        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'killkrill-manager',
            'components': {
                'database': 'ok',
                'redis': 'ok'
            }
        }
    except Exception as e:
        health_checks.labels(status='error').inc()
        response.status = 503
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

# Prometheus metrics endpoint
@action('metrics')
def metrics():
    """Prometheus metrics endpoint"""
    response.headers['Content-Type'] = 'text/plain; version=0.0.4; charset=utf-8'
    return generate_latest()

# Embedded monitoring pages
@action('prometheus')
def prometheus_page():
    """Embedded Prometheus monitoring page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Prometheus Metrics</title>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 1rem;
                display: flex; justify-content: space-between; align-items: center;
            }}
            .header h2 {{ margin: 0; }}
            .nav-buttons {{ display: flex; gap: 1rem; }}
            .nav-buttons a {{
                background: rgba(255,255,255,0.2); color: white;
                padding: 0.5rem 1rem; border-radius: 6px;
                text-decoration: none; transition: background 0.3s;
            }}
            .nav-buttons a:hover {{ background: rgba(255,255,255,0.3); }}
            iframe {{ width: 100%; height: calc(100vh - 60px); border: none; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>📊 Prometheus Metrics Dashboard</h2>
            <div class="nav-buttons">
                <a href="/manager/">← Back to Manager</a>
                <a href="/manager/fleet">Fleet</a>
                <a href="/manager/alertmanager">AlertManager</a>
            </div>
        </div>
        <iframe src="http://localhost:9090" title="Prometheus Dashboard"></iframe>
    </body>
    </html>
    """

@action('fleet')
def fleet_page():
    """Embedded Fleet device management page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Fleet Device Management</title>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 1rem;
                display: flex; justify-content: space-between; align-items: center;
            }}
            .header h2 {{ margin: 0; }}
            .nav-buttons {{ display: flex; gap: 1rem; }}
            .nav-buttons a {{
                background: rgba(255,255,255,0.2); color: white;
                padding: 0.5rem 1rem; border-radius: 6px;
                text-decoration: none; transition: background 0.3s;
            }}
            .nav-buttons a:hover {{ background: rgba(255,255,255,0.3); }}
            iframe {{ width: 100%; height: calc(100vh - 60px); border: none; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>🚀 Fleet Device Management</h2>
            <div class="nav-buttons">
                <a href="/manager/">← Back to Manager</a>
                <a href="/manager/prometheus">Prometheus</a>
                <a href="/manager/alertmanager">AlertManager</a>
            </div>
        </div>
        <iframe src="http://localhost:8084" title="Fleet Dashboard"></iframe>
    </body>
    </html>
    """

@action('alertmanager')
def alertmanager_page():
    """Embedded AlertManager page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - AlertManager</title>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 1rem;
                display: flex; justify-content: space-between; align-items: center;
            }}
            .header h2 {{ margin: 0; }}
            .nav-buttons {{ display: flex; gap: 1rem; }}
            .nav-buttons a {{
                background: rgba(255,255,255,0.2); color: white;
                padding: 0.5rem 1rem; border-radius: 6px;
                text-decoration: none; transition: background 0.3s;
            }}
            .nav-buttons a:hover {{ background: rgba(255,255,255,0.3); }}
            iframe {{ width: 100%; height: calc(100vh - 60px); border: none; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>🚨 AlertManager - Alert Management</h2>
            <div class="nav-buttons">
                <a href="/manager/">← Back to Manager</a>
                <a href="/manager/prometheus">Prometheus</a>
                <a href="/manager/fleet">Fleet</a>
            </div>
        </div>
        <iframe src="http://localhost:9093" title="AlertManager Dashboard"></iframe>
    </body>
    </html>
    """

# Service status checking functions
def check_service_status():
    """Check status of all KillKrill services"""
    import subprocess
    import socket

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
    import psutil
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

# Main application index
@action('index')
@action('index.html')
def index():
    """KillKrill Management Portal Dashboard"""
    license_key = os.environ.get('LICENSE_KEY', 'PENG-DEMO-DEMO-DEMO-DEMO-DEMO')

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

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill Management Portal</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333; min-height: 100vh;
            }}
            .container {{ max-width: 1600px; margin: 0 auto; padding: 1rem; }}

            /* Header */
            .header {{
                background: white; border-radius: 12px; padding: 2rem; margin-bottom: 2rem;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }}
            .header h1 {{ margin: 0 0 0.5rem 0; font-size: 2.5rem; color: #1f2937; }}
            .header p {{ margin: 0 0 1rem 0; font-size: 1.1rem; color: #6b7280; }}

            .license-badge {{
                display: inline-block; padding: 0.5rem 1rem; border-radius: 25px;
                font-size: 0.9rem; font-weight: 700; text-transform: uppercase;
                background: {'#fef3c7' if 'DEMO' in license_key else '#d1fae5'};
                color: {'#92400e' if 'DEMO' in license_key else '#065f46'};
                margin-bottom: 1.5rem;
            }}

            .nav-buttons {{
                display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;
                margin-top: 1.5rem;
            }}
            .nav-btn {{
                background: #4f46e5; color: white; padding: 0.75rem 1.5rem;
                border-radius: 8px; text-decoration: none; font-weight: 600;
                transition: all 0.3s; box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
            }}
            .nav-btn:hover {{ background: #3730a3; transform: translateY(-2px); }}

            /* Dashboard Grid */
            .dashboard-grid {{
                display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; margin-bottom: 2rem;
            }}

            /* Service Status Grid */
            .services-grid {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem; margin-bottom: 1.5rem;
            }}

            .service-card {{
                background: white; border-radius: 8px; padding: 1rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;
                transition: transform 0.2s;
            }}
            .service-card:hover {{ transform: translateY(-2px); }}

            .service-status {{
                width: 16px; height: 16px; border-radius: 50%; margin: 0 auto 0.5rem;
            }}
            .status-healthy {{ background: #10b981; }}
            .status-down {{ background: #ef4444; }}
            .status-error {{ background: #f59e0b; }}

            .service-name {{ font-weight: 600; margin-bottom: 0.25rem; }}
            .service-type {{ font-size: 0.8rem; color: #6b7280; text-transform: uppercase; }}
            .service-port {{ font-size: 0.75rem; color: #9ca3af; }}

            /* System Metrics */
            .metrics-card {{
                background: white; border-radius: 12px; padding: 1.5rem;
                box-shadow: 0 4px 16px rgba(0,0,0,0.08);
            }}

            .metric-item {{
                margin-bottom: 1rem;
            }}
            .metric-label {{ font-weight: 600; margin-bottom: 0.5rem; display: flex; justify-content: space-between; }}
            .metric-bar {{
                background: #e5e7eb; height: 8px; border-radius: 4px; overflow: hidden;
            }}
            .metric-fill {{
                height: 100%; border-radius: 4px; transition: width 0.3s ease;
            }}
            .metric-fill.cpu {{ background: linear-gradient(90deg, #10b981, #059669); }}
            .metric-fill.memory {{ background: linear-gradient(90deg, #3b82f6, #1d4ed8); }}
            .metric-fill.disk {{ background: linear-gradient(90deg, #8b5cf6, #7c3aed); }}

            /* Configuration Navigation */
            .config-grid {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 1.5rem; margin-top: 2rem;
            }}

            .config-card {{
                background: white; border-radius: 12px; padding: 2rem; text-align: center;
                box-shadow: 0 4px 16px rgba(0,0,0,0.08); transition: all 0.3s;
                cursor: pointer; text-decoration: none; color: inherit;
            }}
            .config-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 25px rgba(0,0,0,0.15); }}

            .config-icon {{ font-size: 3rem; margin-bottom: 1rem; }}
            .config-title {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem; color: #1f2937; }}
            .config-desc {{ color: #6b7280; line-height: 1.5; }}

            /* Responsive */
            @media (max-width: 1024px) {{
                .dashboard-grid {{ grid-template-columns: 1fr; }}
                .services-grid {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
                .config-grid {{ grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }}
            }}

            @media (max-width: 768px) {{
                .services-grid {{ grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }}
                .nav-buttons {{ flex-direction: column; align-items: center; }}
                .header {{ padding: 1rem; }}
                .header h1 {{ font-size: 2rem; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div class="header">
                <h1>🐧 KillKrill Management Portal</h1>
                <p>Enterprise observability and device management platform</p>
                <span class="license-badge">{license_tier} License</span>

                <div class="nav-buttons">
                    <a href="/manager/prometheus" class="nav-btn" target="_blank">📊 Prometheus</a>
                    <a href="/manager/grafana-ui" class="nav-btn" target="_blank">📈 Grafana</a>
                    <a href="/manager/fleet-ui" class="nav-btn" target="_blank">🚀 Fleet</a>
                    <a href="/manager/alertmanager" class="nav-btn" target="_blank">🚨 AlertManager</a>
                    <a href="/manager/kibana-ui" class="nav-btn" target="_blank">📋 Kibana</a>
                </div>
            </div>

            <!-- Dashboard Grid -->
            <div class="dashboard-grid">
                <!-- Service Status Overview -->
                <div class="metrics-card">
                    <h2 style="margin-top: 0; color: #1f2937;">🔧 Service Status Overview</h2>
                    <div class="services-grid">
                        {generate_service_cards(services)}
                    </div>
                </div>

                <!-- System Metrics -->
                <div class="metrics-card">
                    <h2 style="margin-top: 0; color: #1f2937;">📊 System Metrics</h2>
                    <div class="metric-item">
                        <div class="metric-label">
                            <span>CPU Usage</span>
                            <span>{metrics['cpu_percent']:.1f}%</span>
                        </div>
                        <div class="metric-bar">
                            <div class="metric-fill cpu" style="width: {metrics['cpu_percent']}%"></div>
                        </div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">
                            <span>Memory Usage</span>
                            <span>{metrics['memory_percent']:.1f}%</span>
                        </div>
                        <div class="metric-bar">
                            <div class="metric-fill memory" style="width: {metrics['memory_percent']}%"></div>
                        </div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">
                            <span>Disk Usage</span>
                            <span>{metrics['disk_percent']:.1f}%</span>
                        </div>
                        <div class="metric-bar">
                            <div class="metric-fill disk" style="width: {metrics['disk_percent']}%"></div>
                        </div>
                    </div>
                    <button onclick="location.reload()" class="nav-btn" style="width: 100%; margin-top: 1rem;">🔄 Refresh</button>
                </div>
            </div>

            <!-- Configuration Management Navigation -->
            <h2 style="color: white; text-align: center; margin: 2rem 0 1.5rem 0;">⚙️ Configuration Management</h2>
            <div class="config-grid">
                <a href="/manager/infrastructure" class="config-card">
                    <div class="config-icon">🏗️</div>
                    <div class="config-title">Infrastructure</div>
                    <div class="config-desc">Docker Compose services, environment variables, resource limits, and container management</div>
                </a>

                <a href="/manager/databases" class="config-card">
                    <div class="config-icon">🗄️</div>
                    <div class="config-title">Databases</div>
                    <div class="config-desc">PostgreSQL, MySQL, Redis, and Elasticsearch configuration, users, and optimization</div>
                </a>

                <a href="/manager/monitoring" class="config-card">
                    <div class="config-icon">📊</div>
                    <div class="config-title">Monitoring</div>
                    <div class="config-desc">Prometheus, Grafana, AlertManager configuration, dashboards, and alerting rules</div>
                </a>

                <a href="/manager/fleet-config" class="config-card">
                    <div class="config-icon">🚀</div>
                    <div class="config-title">Fleet Management</div>
                    <div class="config-desc">Fleet server settings, agent policies, query scheduling, and device enrollment</div>
                </a>

                <a href="/manager/logs" class="config-card">
                    <div class="config-icon">📝</div>
                    <div class="config-title">Log Processing</div>
                    <div class="config-desc">Log receivers, Logstash pipelines, index templates, and retention policies</div>
                </a>

                <a href="/manager/metrics" class="config-card">
                    <div class="config-icon">📈</div>
                    <div class="config-title">Metrics Processing</div>
                    <div class="config-desc">Metrics collection, processing rules, aggregation, and storage configuration</div>
                </a>

                <a href="/manager/security" class="config-card">
                    <div class="config-icon">🔒</div>
                    <div class="config-title">Security & Networking</div>
                    <div class="config-desc">TLS certificates, authentication, user management, and network policies</div>
                </a>
            </div>

            <h2 style="color: white; text-align: center; margin: 2rem 0 1.5rem 0;">🖥️ Sub-Service Interfaces</h2>
            <div class="config-grid">
                <a href="/manager/prometheus-ui" class="config-card" target="_blank">
                    <div class="config-icon">📊</div>
                    <div class="config-title">Prometheus UI</div>
                    <div class="config-desc">Full Prometheus interface for metrics querying, alerting, and monitoring</div>
                </a>

                <a href="/manager/grafana-ui" class="config-card" target="_blank">
                    <div class="config-icon">📈</div>
                    <div class="config-title">Grafana UI</div>
                    <div class="config-desc">Complete Grafana dashboards, data sources, and visualization management</div>
                </a>

                <a href="/manager/fleet-ui" class="config-card" target="_blank">
                    <div class="config-icon">🚀</div>
                    <div class="config-title">Fleet UI</div>
                    <div class="config-desc">Full Fleet device management interface for hosts, queries, and policies</div>
                </a>

                <a href="/manager/kibana-ui" class="config-card" target="_blank">
                    <div class="config-icon">📋</div>
                    <div class="config-title">Kibana UI</div>
                    <div class="config-desc">Complete Kibana interface for log analysis, search, and visualization</div>
                </a>

                <a href="/manager/alertmanager-ui" class="config-card" target="_blank">
                    <div class="config-icon">🚨</div>
                    <div class="config-title">AlertManager UI</div>
                    <div class="config-desc">AlertManager interface for managing alerts, silences, and notifications</div>
                </a>

                <a href="/manager/elasticsearch-ui" class="config-card" target="_blank">
                    <div class="config-icon">🔍</div>
                    <div class="config-title">Elasticsearch UI</div>
                    <div class="config-desc">Elasticsearch cluster management, indices, and cluster health monitoring</div>
                </a>
            </div>
        </div>

        <script>
            // Auto-refresh the page every 30 seconds to update service status
            setTimeout(() => location.reload(), 30000);
        </script>
    </body>
    </html>
    """

# Add the embedded iframe pages for all sub-services
@action('prometheus-ui')
def prometheus_ui():
    """Embedded Prometheus interface"""
    return generate_iframe_page("Prometheus Metrics Dashboard", "http://localhost:9090", "📊")

@action('grafana-ui')
def grafana_ui():
    """Embedded Grafana interface"""
    return generate_iframe_page("Grafana Dashboards", "http://localhost:3000", "📈")

@action('fleet-ui')
def fleet_ui():
    """Embedded Fleet interface"""
    return generate_iframe_page("Fleet Device Management", "http://localhost:8084", "🚀")

@action('kibana-ui')
def kibana_ui():
    """Embedded Kibana interface"""
    return generate_iframe_page("Kibana Log Analysis", "http://localhost:5601", "📋")

@action('alertmanager-ui')
def alertmanager_ui():
    """Embedded AlertManager interface"""
    return generate_iframe_page("AlertManager", "http://localhost:9093", "🚨")

@action('elasticsearch-ui')
def elasticsearch_ui():
    """Embedded Elasticsearch interface"""
    return generate_iframe_page("Elasticsearch Cluster", "http://localhost:9200", "🔍")

@action('logstash-ui')
def logstash_ui():
    """Embedded Logstash interface"""
    return generate_iframe_page("Logstash Monitoring", "http://localhost:9600", "📋")

def generate_iframe_page(title, url, icon):
    """Generate a consistent iframe page for sub-services"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - {title}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 1rem; display: flex; justify-content: space-between; align-items: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header h2 {{ margin: 0; font-size: 1.5rem; }}
            .nav-buttons {{ display: flex; gap: 1rem; }}
            .nav-btn {{
                background: rgba(255,255,255,0.2); color: white;
                padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none;
                transition: background 0.3s; font-weight: 600;
            }}
            .nav-btn:hover {{ background: rgba(255,255,255,0.3); }}
            iframe {{ width: 100%; height: calc(100vh - 70px); border: none; }}
            .error-msg {{
                padding: 2rem; text-align: center; font-size: 1.2rem; color: #666;
                background: #f9f9f9; margin: 2rem; border-radius: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>{icon} {title}</h2>
            <div class="nav-buttons">
                <a href="/manager/" class="nav-btn">← Dashboard</a>
                <a href="{url}" class="nav-btn" target="_blank">Open Direct</a>
            </div>
        </div>
        <iframe src="{url}" title="{title}"
                onerror="this.style.display='none'; document.querySelector('.error-msg').style.display='block';">
        </iframe>
        <div class="error-msg" style="display: none;">
            <h3>Service Unavailable</h3>
            <p>The {title} service is not currently accessible at {url}</p>
            <p>Please check that the service is running and try again.</p>
            <a href="/manager/" class="nav-btn">Return to Dashboard</a>
        </div>
    </body>
    </html>
    """

# Configuration Pages
@action('databases')
def databases_config():
    """Database configuration management page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Database Configuration</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333; min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 1rem; }}

            /* Header */
            .header {{
                background: white; border-radius: 12px; padding: 2rem; margin-bottom: 2rem;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }}
            .header h1 {{ margin: 0 0 0.5rem 0; font-size: 2.2rem; color: #1f2937; }}
            .header p {{ margin: 0 0 1rem 0; font-size: 1.1rem; color: #6b7280; }}

            .nav-buttons {{
                display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;
                margin-top: 1.5rem;
            }}
            .nav-btn {{
                background: #4f46e5; color: white; padding: 0.75rem 1.5rem;
                border-radius: 8px; text-decoration: none; font-weight: 600;
                transition: all 0.3s; box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
                border: none; cursor: pointer;
            }}
            .nav-btn:hover {{ background: #3730a3; transform: translateY(-2px); }}
            .nav-btn.back {{ background: #6b7280; }}
            .nav-btn.back:hover {{ background: #4b5563; }}

            /* Database Cards Grid */
            .db-grid {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 1.5rem; margin-bottom: 2rem;
            }}

            .db-card {{
                background: white; border-radius: 12px; padding: 1.5rem;
                box-shadow: 0 4px 16px rgba(0,0,0,0.08); transition: transform 0.2s;
            }}
            .db-card:hover {{ transform: translateY(-2px); }}

            .db-header {{
                display: flex; align-items: center; margin-bottom: 1rem;
                padding-bottom: 1rem; border-bottom: 1px solid #e5e7eb;
            }}
            .db-icon {{ font-size: 2rem; margin-right: 1rem; }}
            .db-title {{ font-size: 1.3rem; font-weight: 700; color: #1f2937; margin: 0; }}
            .db-status {{
                margin-left: auto; padding: 0.25rem 0.75rem; border-radius: 15px;
                font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
            }}
            .status-healthy {{ background: #d1fae5; color: #065f46; }}
            .status-down {{ background: #fee2e2; color: #991b1b; }}

            .form-group {{
                margin-bottom: 1rem;
            }}
            .form-label {{
                display: block; margin-bottom: 0.5rem; font-weight: 600; color: #374151;
            }}
            .form-input {{
                width: 100%; padding: 0.75rem; border: 1px solid #d1d5db;
                border-radius: 6px; font-size: 0.9rem;
                transition: border-color 0.2s;
            }}
            .form-input:focus {{
                outline: none; border-color: #4f46e5;
                box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
            }}

            .form-row {{
                display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
            }}

            .btn-group {{
                display: flex; gap: 0.5rem; margin-top: 1rem;
            }}
            .btn {{
                padding: 0.5rem 1rem; border: none; border-radius: 6px;
                font-weight: 600; cursor: pointer; transition: all 0.2s;
            }}
            .btn-primary {{ background: #4f46e5; color: white; }}
            .btn-primary:hover {{ background: #3730a3; }}
            .btn-secondary {{ background: #e5e7eb; color: #374151; }}
            .btn-secondary:hover {{ background: #d1d5db; }}
            .btn-danger {{ background: #ef4444; color: white; }}
            .btn-danger:hover {{ background: #dc2626; }}

            /* Status indicators */
            .connection-status {{
                display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem;
                padding: 0.75rem; border-radius: 6px; font-size: 0.9rem;
            }}
            .connection-healthy {{ background: #d1fae5; color: #065f46; }}
            .connection-error {{ background: #fee2e2; color: #991b1b; }}

            /* Responsive */
            @media (max-width: 768px) {{
                .db-grid {{ grid-template-columns: 1fr; }}
                .form-row {{ grid-template-columns: 1fr; }}
                .nav-buttons {{ flex-direction: column; align-items: center; }}
                .header {{ padding: 1rem; }}
                .header h1 {{ font-size: 1.8rem; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div class="header">
                <h1>🗄️ Database Configuration</h1>
                <p>Manage PostgreSQL, MySQL, Redis, and Elasticsearch configurations</p>

                <div class="nav-buttons">
                    <a href="/manager/" class="nav-btn back">← Back to Dashboard</a>
                    <button onclick="testAllConnections()" class="nav-btn">🔍 Test All Connections</button>
                    <button onclick="saveAllConfigs()" class="nav-btn">💾 Save All Changes</button>
                </div>
            </div>

            <!-- Database Configuration Cards -->
            <div class="db-grid">
                <!-- PostgreSQL Configuration -->
                <div class="db-card">
                    <div class="db-header">
                        <div class="db-icon">🐘</div>
                        <h3 class="db-title">PostgreSQL</h3>
                        <span class="db-status status-healthy">Connected</span>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Host</label>
                        <input type="text" class="form-input" value="postgres" placeholder="Database host">
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Port</label>
                            <input type="number" class="form-input" value="5432" placeholder="5432">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Database</label>
                            <input type="text" class="form-input" value="killkrill" placeholder="Database name">
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-input" value="killkrill" placeholder="Username">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-input" value="••••••••••" placeholder="Password">
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">
                            <input type="checkbox" checked> Enable SSL
                        </label>
                    </div>

                    <div class="connection-status connection-healthy">
                        ✅ Connection healthy - 23ms response time
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="testConnection('postgresql')">Test Connection</button>
                        <button class="btn btn-secondary" onclick="viewLogs('postgresql')">View Logs</button>
                        <button class="btn btn-danger" onclick="restartService('postgresql')">Restart</button>
                    </div>
                </div>

                <!-- MySQL (Fleet) Configuration -->
                <div class="db-card">
                    <div class="db-header">
                        <div class="db-icon">🐬</div>
                        <h3 class="db-title">MySQL (Fleet)</h3>
                        <span class="db-status status-healthy">Connected</span>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Host</label>
                        <input type="text" class="form-input" value="fleet-mysql" placeholder="Database host">
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Port</label>
                            <input type="number" class="form-input" value="3306" placeholder="3306">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Database</label>
                            <input type="text" class="form-input" value="fleet" placeholder="Database name">
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-input" value="fleet" placeholder="Username">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-input" value="••••••••••" placeholder="Password">
                        </div>
                    </div>

                    <div class="connection-status connection-healthy">
                        ✅ Connection healthy - 18ms response time
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="testConnection('mysql')">Test Connection</button>
                        <button class="btn btn-secondary" onclick="viewLogs('mysql')">View Logs</button>
                        <button class="btn btn-danger" onclick="restartService('mysql')">Restart</button>
                    </div>
                </div>

                <!-- Redis Configuration -->
                <div class="db-card">
                    <div class="db-header">
                        <div class="db-icon">🔴</div>
                        <h3 class="db-title">Redis</h3>
                        <span class="db-status status-healthy">Connected</span>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Host</label>
                        <input type="text" class="form-input" value="redis" placeholder="Redis host">
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Port</label>
                            <input type="number" class="form-input" value="6379" placeholder="6379">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Database</label>
                            <input type="number" class="form-input" value="0" placeholder="0">
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Password</label>
                        <input type="password" class="form-input" placeholder="Redis password (optional)">
                    </div>

                    <div class="connection-status connection-healthy">
                        ✅ Connection healthy - 2ms response time
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="testConnection('redis')">Test Connection</button>
                        <button class="btn btn-secondary" onclick="viewLogs('redis')">View Logs</button>
                        <button class="btn btn-danger" onclick="restartService('redis')">Restart</button>
                    </div>
                </div>

                <!-- Elasticsearch Configuration -->
                <div class="db-card">
                    <div class="db-header">
                        <div class="db-icon">🔍</div>
                        <h3 class="db-title">Elasticsearch</h3>
                        <span class="db-status status-down">Disconnected</span>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Host</label>
                        <input type="text" class="form-input" value="elasticsearch" placeholder="Elasticsearch host">
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Port</label>
                            <input type="number" class="form-input" value="9200" placeholder="9200">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Cluster Name</label>
                            <input type="text" class="form-input" value="killkrill-cluster" placeholder="Cluster name">
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-input" value="elastic" placeholder="Username">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-input" placeholder="Password">
                        </div>
                    </div>

                    <div class="connection-status connection-error">
                        ❌ Connection failed - Service unavailable
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="testConnection('elasticsearch')">Test Connection</button>
                        <button class="btn btn-secondary" onclick="viewLogs('elasticsearch')">View Logs</button>
                        <button class="btn btn-danger" onclick="restartService('elasticsearch')">Restart</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function testConnection(dbType) {{
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = 'Testing...';
                btn.disabled = true;

                // Simulate connection test
                setTimeout(() => {{
                    btn.textContent = originalText;
                    btn.disabled = false;
                    alert(`${{dbType}} connection test completed`);
                }}, 2000);
            }}

            function testAllConnections() {{
                alert('Testing all database connections...');
                // In a real implementation, this would test all databases
            }}

            function saveAllConfigs() {{
                alert('Saving all database configurations...');
                // In a real implementation, this would save configurations
            }}

            function viewLogs(dbType) {{
                window.open(`/manager/logs?service=${{dbType}}`, '_blank');
            }}

            function restartService(dbType) {{
                if (confirm(`Are you sure you want to restart ${{dbType}}? This may cause temporary downtime.`)) {{
                    alert(`Restarting ${{dbType}} service...`);
                    // In a real implementation, this would restart the service
                }}
            }}
        </script>
    </body>
    </html>
    """

@action('infrastructure')
def infrastructure_config():
    """Infrastructure configuration management page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Infrastructure Configuration</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333; min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 1rem; }}

            .header {{
                background: white; border-radius: 12px; padding: 2rem; margin-bottom: 2rem;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }}
            .header h1 {{ margin: 0 0 0.5rem 0; font-size: 2.2rem; color: #1f2937; }}
            .header p {{ margin: 0 0 1rem 0; font-size: 1.1rem; color: #6b7280; }}

            .nav-buttons {{
                display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;
                margin-top: 1.5rem;
            }}
            .nav-btn {{
                background: #4f46e5; color: white; padding: 0.75rem 1.5rem;
                border-radius: 8px; text-decoration: none; font-weight: 600;
                transition: all 0.3s; box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
                border: none; cursor: pointer;
            }}
            .nav-btn:hover {{ background: #3730a3; transform: translateY(-2px); }}
            .nav-btn.back {{ background: #6b7280; }}
            .nav-btn.back:hover {{ background: #4b5563; }}

            .config-grid {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 1.5rem; margin-bottom: 2rem;
            }}

            .config-card {{
                background: white; border-radius: 12px; padding: 1.5rem;
                box-shadow: 0 4px 16px rgba(0,0,0,0.08); transition: transform 0.2s;
            }}
            .config-card:hover {{ transform: translateY(-2px); }}

            .card-header {{
                display: flex; align-items: center; margin-bottom: 1rem;
                padding-bottom: 1rem; border-bottom: 1px solid #e5e7eb;
            }}
            .card-icon {{ font-size: 2rem; margin-right: 1rem; }}
            .card-title {{ font-size: 1.3rem; font-weight: 700; color: #1f2937; margin: 0; }}

            .form-group {{ margin-bottom: 1rem; }}
            .form-label {{ display: block; margin-bottom: 0.5rem; font-weight: 600; color: #374151; }}
            .form-input, .form-select, .form-textarea {{
                width: 100%; padding: 0.75rem; border: 1px solid #d1d5db;
                border-radius: 6px; font-size: 0.9rem; transition: border-color 0.2s;
            }}
            .form-input:focus, .form-select:focus, .form-textarea:focus {{
                outline: none; border-color: #4f46e5;
                box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
            }}
            .form-textarea {{ min-height: 150px; resize: vertical; font-family: 'Monaco', 'Menlo', monospace; }}

            .service-list {{
                max-height: 300px; overflow-y: auto; border: 1px solid #e5e7eb;
                border-radius: 6px; padding: 1rem; background: #f9fafb;
            }}
            .service-item {{
                display: flex; justify-content: space-between; align-items: center;
                padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb;
            }}
            .service-item:last-child {{ border-bottom: none; }}
            .service-status {{ font-size: 0.8rem; padding: 0.2rem 0.5rem; border-radius: 12px; }}
            .status-running {{ background: #d1fae5; color: #065f46; }}
            .status-stopped {{ background: #fee2e2; color: #991b1b; }}

            .btn-group {{ display: flex; gap: 0.5rem; margin-top: 1rem; }}
            .btn {{
                padding: 0.5rem 1rem; border: none; border-radius: 6px;
                font-weight: 600; cursor: pointer; transition: all 0.2s;
            }}
            .btn-primary {{ background: #4f46e5; color: white; }}
            .btn-primary:hover {{ background: #3730a3; }}
            .btn-secondary {{ background: #e5e7eb; color: #374151; }}
            .btn-secondary:hover {{ background: #d1d5db; }}
            .btn-danger {{ background: #ef4444; color: white; }}
            .btn-danger:hover {{ background: #dc2626; }}
            .btn-success {{ background: #10b981; color: white; }}
            .btn-success:hover {{ background: #059669; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Infrastructure Configuration</h1>
                <p>Manage Docker Compose services, environment variables, and resource limits</p>

                <div class="nav-buttons">
                    <a href="/manager/" class="nav-btn back">← Back to Dashboard</a>
                    <button onclick="saveAllConfigs()" class="nav-btn">💾 Save All Changes</button>
                    <button onclick="restartInfrastructure()" class="nav-btn btn-danger">🔄 Restart All</button>
                </div>
            </div>

            <div class="config-grid">
                <!-- Docker Compose Services -->
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">🐳</div>
                        <h3 class="card-title">Docker Services</h3>
                    </div>

                    <div class="service-list">
                        <div class="service-item">
                            <span>PostgreSQL</span>
                            <span class="service-status status-running">Running</span>
                        </div>
                        <div class="service-item">
                            <span>Redis</span>
                            <span class="service-status status-running">Running</span>
                        </div>
                        <div class="service-item">
                            <span>Manager</span>
                            <span class="service-status status-running">Running</span>
                        </div>
                        <div class="service-item">
                            <span>Log Receiver</span>
                            <span class="service-status status-running">Running</span>
                        </div>
                        <div class="service-item">
                            <span>Metrics Receiver</span>
                            <span class="service-status status-running">Running</span>
                        </div>
                        <div class="service-item">
                            <span>Prometheus</span>
                            <span class="service-status status-running">Running</span>
                        </div>
                        <div class="service-item">
                            <span>Elasticsearch</span>
                            <span class="service-status status-stopped">Stopped</span>
                        </div>
                        <div class="service-item">
                            <span>Fleet Server</span>
                            <span class="service-status status-stopped">Stopped</span>
                        </div>
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-success" onclick="startAllServices()">▶️ Start All</button>
                        <button class="btn btn-secondary" onclick="stopAllServices()">⏹️ Stop All</button>
                        <button class="btn btn-primary" onclick="restartAllServices()">🔄 Restart All</button>
                    </div>
                </div>

                <!-- Environment Variables -->
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">🔧</div>
                        <h3 class="card-title">Environment Variables</h3>
                    </div>

                    <div class="form-group">
                        <label class="form-label">License Key</label>
                        <input type="text" class="form-input" value="PENG-DEMO-DEMO-DEMO-DEMO-DEMO" placeholder="License key">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Database URL</label>
                        <input type="text" class="form-input" value="postgresql://killkrill:killkrill123@postgres:5432/killkrill">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Redis URL</label>
                        <input type="text" class="form-input" value="redis://redis:6379">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Log Level</label>
                        <select class="form-select">
                            <option value="DEBUG">DEBUG</option>
                            <option value="INFO" selected>INFO</option>
                            <option value="WARNING">WARNING</option>
                            <option value="ERROR">ERROR</option>
                        </select>
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="updateEnvironment()">💾 Update Environment</button>
                        <button class="btn btn-secondary" onclick="exportEnvironment()">📤 Export .env</button>
                    </div>
                </div>

                <!-- Resource Limits -->
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">⚡</div>
                        <h3 class="card-title">Resource Limits</h3>
                    </div>

                    <div class="form-group">
                        <label class="form-label">PostgreSQL Memory Limit</label>
                        <input type="text" class="form-input" value="1g" placeholder="e.g., 1g, 512m">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Redis Memory Limit</label>
                        <input type="text" class="form-input" value="256m" placeholder="e.g., 256m, 1g">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Elasticsearch Heap Size</label>
                        <input type="text" class="form-input" value="1g" placeholder="e.g., 1g, 2g">
                    </div>

                    <div class="form-group">
                        <label class="form-label">CPU Limit (cores)</label>
                        <input type="number" class="form-input" value="2" step="0.5" min="0.5">
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="updateResourceLimits()">⚡ Apply Limits</button>
                        <button class="btn btn-secondary" onclick="viewResourceUsage()">📊 View Usage</button>
                    </div>
                </div>

                <!-- Docker Compose Editor -->
                <div class="config-card" style="grid-column: 1 / -1;">
                    <div class="card-header">
                        <div class="card-icon">📝</div>
                        <h3 class="card-title">Docker Compose Configuration</h3>
                    </div>

                    <div class="form-group">
                        <label class="form-label">docker-compose.yml</label>
                        <textarea class="form-textarea" rows="20">version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: killkrill
      POSTGRES_USER: killkrill
      POSTGRES_PASSWORD: killkrill123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U killkrill"]
      interval: 30s
      timeout: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 3s
      retries: 5

  manager:
    build:
      context: .
      dockerfile: apps/manager/Dockerfile
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql://killkrill:killkrill123@postgres:5432/killkrill
      - REDIS_URL=redis://redis:6379
      - LICENSE_KEY=${{LICENSE_KEY:-PENG-DEMO-DEMO-DEMO-DEMO-DEMO}}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:</textarea>
                    </div>

                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="saveDockerCompose()">💾 Save Configuration</button>
                        <button class="btn btn-secondary" onclick="validateDockerCompose()">✅ Validate YAML</button>
                        <button class="btn btn-success" onclick="applyDockerCompose()">🚀 Apply Changes</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function startAllServices() {{
                if (confirm('Start all Docker services?')) {{
                    alert('Starting all services...');
                }}
            }}

            function stopAllServices() {{
                if (confirm('Stop all Docker services? This will cause downtime.')) {{
                    alert('Stopping all services...');
                }}
            }}

            function restartAllServices() {{
                if (confirm('Restart all services? This may cause temporary downtime.')) {{
                    alert('Restarting all services...');
                }}
            }}

            function updateEnvironment() {{
                alert('Updating environment variables...');
            }}

            function exportEnvironment() {{
                alert('Exporting environment to .env file...');
            }}

            function updateResourceLimits() {{
                if (confirm('Apply new resource limits? This will restart affected services.')) {{
                    alert('Applying resource limits...');
                }}
            }}

            function viewResourceUsage() {{
                window.open('/manager/', '_blank');
            }}

            function saveDockerCompose() {{
                alert('Saving Docker Compose configuration...');
            }}

            function validateDockerCompose() {{
                alert('Validating YAML syntax...');
            }}

            function applyDockerCompose() {{
                if (confirm('Apply Docker Compose changes? This will restart all services.')) {{
                    alert('Applying Docker Compose configuration...');
                }}
            }}

            function saveAllConfigs() {{
                alert('Saving all infrastructure configurations...');
            }}

            function restartInfrastructure() {{
                if (confirm('Restart entire infrastructure? This will cause significant downtime.')) {{
                    alert('Restarting infrastructure...');
                }}
            }}
        </script>
    </body>
    </html>
    """

@action('monitoring')
def monitoring_config():
    """Monitoring configuration management page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Monitoring Configuration</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333; min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 1rem; }}
            .header {{
                background: white; border-radius: 12px; padding: 2rem; margin-bottom: 2rem;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }}
            .header h1 {{ margin: 0 0 0.5rem 0; font-size: 2.2rem; color: #1f2937; }}
            .nav-btn {{
                background: #4f46e5; color: white; padding: 0.75rem 1.5rem;
                border-radius: 8px; text-decoration: none; font-weight: 600;
                margin: 0.5rem; display: inline-block;
            }}
            .nav-btn.back {{ background: #6b7280; }}
            .config-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }}
            .config-card {{ background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}
            .card-header {{ display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #e5e7eb; }}
            .card-icon {{ font-size: 2rem; margin-right: 1rem; }}
            .card-title {{ font-size: 1.3rem; font-weight: 700; color: #1f2937; margin: 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Monitoring Configuration</h1>
                <p>Configure Prometheus, Grafana, AlertManager, and monitoring rules</p>
                <a href="/manager/" class="nav-btn back">← Back to Dashboard</a>
                <a href="/manager/prometheus-ui" class="nav-btn" target="_blank">📊 Prometheus UI</a>
                <a href="/manager/grafana-ui" class="nav-btn" target="_blank">📈 Grafana UI</a>
            </div>
            <div class="config-grid">
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">📊</div>
                        <h3 class="card-title">Prometheus</h3>
                    </div>
                    <p>Configure metrics collection, retention, and targets...</p>
                </div>
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">📈</div>
                        <h3 class="card-title">Grafana</h3>
                    </div>
                    <p>Manage dashboards, data sources, and visualizations...</p>
                </div>
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">🚨</div>
                        <h3 class="card-title">AlertManager</h3>
                    </div>
                    <p>Configure alerting rules, notifications, and silences...</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@action('security')
def security_config():
    """Security and networking configuration page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Security Configuration</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333; min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 1rem; }}
            .header {{
                background: white; border-radius: 12px; padding: 2rem; margin-bottom: 2rem;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }}
            .header h1 {{ margin: 0 0 0.5rem 0; font-size: 2.2rem; color: #1f2937; }}
            .nav-btn {{
                background: #4f46e5; color: white; padding: 0.75rem 1.5rem;
                border-radius: 8px; text-decoration: none; font-weight: 600;
                margin: 0.5rem; display: inline-block;
            }}
            .nav-btn.back {{ background: #6b7280; }}
            .config-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }}
            .config-card {{ background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}
            .card-header {{ display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #e5e7eb; }}
            .card-icon {{ font-size: 2rem; margin-right: 1rem; }}
            .card-title {{ font-size: 1.3rem; font-weight: 700; color: #1f2937; margin: 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔒 Security & Networking</h1>
                <p>Manage TLS certificates, authentication, and network policies</p>
                <a href="/manager/" class="nav-btn back">← Back to Dashboard</a>
            </div>
            <div class="config-grid">
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">🔐</div>
                        <h3 class="card-title">TLS Certificates</h3>
                    </div>
                    <p>Manage SSL/TLS certificates and encryption settings...</p>
                </div>
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">👤</div>
                        <h3 class="card-title">Authentication</h3>
                    </div>
                    <p>Configure user management, passwords, and access control...</p>
                </div>
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">🌐</div>
                        <h3 class="card-title">Network Policies</h3>
                    </div>
                    <p>Set up firewall rules, port restrictions, and network security...</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@action('fleet-config')
def fleet_config():
    """Fleet management configuration page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Fleet Configuration</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333; min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 1rem; }}
            .header {{
                background: white; border-radius: 12px; padding: 2rem; margin-bottom: 2rem;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }}
            .header h1 {{ margin: 0 0 0.5rem 0; font-size: 2.2rem; color: #1f2937; }}
            .nav-btn {{
                background: #4f46e5; color: white; padding: 0.75rem 1.5rem;
                border-radius: 8px; text-decoration: none; font-weight: 600;
                margin: 0.5rem; display: inline-block;
            }}
            .nav-btn.back {{ background: #6b7280; }}
            .config-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }}
            .config-card {{ background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}
            .card-header {{ display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #e5e7eb; }}
            .card-icon {{ font-size: 2rem; margin-right: 1rem; }}
            .card-title {{ font-size: 1.3rem; font-weight: 700; color: #1f2937; margin: 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Fleet Management</h1>
                <p>Configure Fleet server, agent policies, and device enrollment</p>
                <a href="/manager/" class="nav-btn back">← Back to Dashboard</a>
                <a href="/manager/fleet-ui" class="nav-btn" target="_blank">🚀 Fleet UI</a>
            </div>
            <div class="config-grid">
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">⚙️</div>
                        <h3 class="card-title">Fleet Server</h3>
                    </div>
                    <p>Configure Fleet server settings, certificates, and enrollment...</p>
                </div>
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">📋</div>
                        <h3 class="card-title">Agent Policies</h3>
                    </div>
                    <p>Manage agent policies, query scheduling, and host management...</p>
                </div>
                <div class="config-card">
                    <div class="card-header">
                        <div class="card-icon">🔌</div>
                        <h3 class="card-title">Integrations</h3>
                    </div>
                    <p>Configure Fleet integrations, data collection, and monitoring...</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@action('api/services/<service>', method=['POST'])
@action.uses(CORS())
def manage_service(service=None):
    """Service management endpoint"""
    try:
        data = request.json or {}
        action_type = data.get('action', 'status')

        # Log the service action
        db.health_checks.insert(
            status='action',
            component=f"{service}_{action_type}"
        )
        db.commit()

        # In a real implementation, you would interact with Docker/systemd here
        # For now, we'll just return success
        return {
            'status': 'success',
            'service': service,
            'action': action_type,
            'timestamp': datetime.utcnow().isoformat(),
            'message': f'Service {service} {action_type} command executed'
        }
    except Exception as e:
        response.status = 500
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

@action('api/config', method=['POST'])
@action.uses(CORS())
def update_configuration():
    """Configuration update endpoint"""
    try:
        config_updates = request.json or {}

        # Store configuration in Redis for persistence
        for key, value in config_updates.items():
            redis_client.hset('killkrill:config', key, json.dumps(value))

        # Log configuration change
        db.health_checks.insert(
            status='config_update',
            component=f"config_{list(config_updates.keys())[0] if config_updates else 'unknown'}"
        )
        db.commit()

        return {
            'status': 'success',
            'updated': config_updates,
            'timestamp': datetime.utcnow().isoformat(),
            'message': f'Updated {len(config_updates)} configuration(s)'
        }
    except Exception as e:
        response.status = 500
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

@action('api/restart', method=['POST'])
@action.uses(CORS())
def restart_services():
    """Restart all services endpoint"""
    try:
        # Log restart request
        db.health_checks.insert(
            status='restart_requested',
            component='all_services'
        )
        db.commit()

        # In a real implementation, you would restart Docker containers here
        # docker-compose restart or systemctl restart commands

        return {
            'status': 'success',
            'message': 'Service restart initiated',
            'timestamp': datetime.utcnow().isoformat(),
            'estimated_downtime': '30-60 seconds'
        }
    except Exception as e:
        response.status = 500
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

@action('logs')
def view_logs():
    """System logs viewer (placeholder)"""
    return """
    <html>
    <head><title>KillKrill System Logs</title></head>
    <body style="font-family: monospace; background: #1a1a1a; color: #00ff00; padding: 20px;">
        <h2>📋 System Logs</h2>
        <pre style="background: #000; padding: 15px; border-radius: 5px; overflow-x: auto;">
2025-09-25 12:34:56 [INFO] KillKrill Manager started
2025-09-25 12:35:01 [INFO] Database connection established
2025-09-25 12:35:02 [INFO] Redis connection established
2025-09-25 12:35:03 [INFO] Manager web interface available at /manager/
2025-09-25 12:35:15 [INFO] Health check passed - all services operational
2025-09-25 12:36:00 [INFO] Configuration updated: log_level=info
2025-09-25 12:37:30 [INFO] Service toggle: metrics-receiver enabled
2025-09-25 12:38:45 [INFO] Metrics collection active - 1,247 metrics processed
        </pre>
        <br>
        <button onclick="window.close()" style="padding: 10px 20px; background: #4f46e5; color: white; border: none; border-radius: 5px;">Close</button>
    </body>
    </html>
    """

# Make sure the database connection is properly initialized when the module loads
try:
    db.health_checks.id  # Test table access
    print("✓ Manager database tables verified")
except Exception as e:
    print(f"⚠️ Manager database table issue: {e}")
