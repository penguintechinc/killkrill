"""
Embedded UI routes (/prometheus-ui, /grafana-ui, /fleet-ui, etc.)
"""

from quart import Blueprint, render_template_string

bp = Blueprint("embeds", __name__)


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
                <a href="/" class="nav-btn">← Dashboard</a>
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
            <a href="/" class="nav-btn">Return to Dashboard</a>
        </div>
    </body>
    </html>
    """


@bp.route("/prometheus-ui", methods=["GET"])
async def prometheus_ui():
    """Embedded Prometheus interface"""
    return await render_template_string(
        generate_iframe_page(
            "Prometheus Metrics Dashboard", "http://localhost:9090", "📊"
        )
    )


@bp.route("/grafana-ui", methods=["GET"])
async def grafana_ui():
    """Embedded Grafana interface"""
    return await render_template_string(
        generate_iframe_page("Grafana Dashboards", "http://localhost:3000", "📈")
    )


@bp.route("/fleet-ui", methods=["GET"])
async def fleet_ui():
    """Embedded Fleet interface"""
    return await render_template_string(
        generate_iframe_page("Fleet Device Management", "http://localhost:8084", "🚀")
    )


@bp.route("/kibana-ui", methods=["GET"])
async def kibana_ui():
    """Embedded Kibana interface"""
    return await render_template_string(
        generate_iframe_page("Kibana Log Analysis", "http://localhost:5601", "📋")
    )


@bp.route("/alertmanager-ui", methods=["GET"])
async def alertmanager_ui():
    """Embedded AlertManager interface"""
    return await render_template_string(
        generate_iframe_page("AlertManager", "http://localhost:9093", "🚨")
    )


@bp.route("/elasticsearch-ui", methods=["GET"])
async def elasticsearch_ui():
    """Embedded Elasticsearch interface"""
    return await render_template_string(
        generate_iframe_page("Elasticsearch Cluster", "http://localhost:9200", "🔍")
    )


@bp.route("/logstash-ui", methods=["GET"])
async def logstash_ui():
    """Embedded Logstash interface"""
    return await render_template_string(
        generate_iframe_page("Logstash Monitoring", "http://localhost:9600", "📋")
    )
