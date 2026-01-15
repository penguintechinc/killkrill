"""
Fleet Integration Module for KillKrill Manager
Provides Fleet UI embedding, SSO integration, and Fleet API management
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
import requests
from py4web import URL, action, redirect, request, response
from py4web.utils.auth import Auth
from py4web.utils.cors import CORS
from pydal import Field

# Fleet server configuration
FLEET_SERVER_URL = os.environ.get("FLEET_SERVER_URL", "http://fleet-server:8080")
FLEET_API_TOKEN = os.environ.get("FLEET_API_TOKEN", "")
JWT_SECRET = os.environ.get("FLEET_JWT_KEY", "supersecretfleetjwtkey123456")


class FleetSSO:
    """Fleet Single Sign-On integration"""

    def __init__(self, db):
        self.db = db
        self._setup_tables()

    def _setup_tables(self):
        """Setup Fleet SSO tables"""
        try:
            # Fleet users mapping table
            self.db.define_table(
                "fleet_users",
                Field("killkrill_user_id", "integer"),
                Field("fleet_user_id", "integer"),
                Field("fleet_api_token", "string"),
                Field("created_at", "datetime", default=datetime.utcnow),
                Field("last_sync", "datetime", default=datetime.utcnow),
                Field("is_active", "boolean", default=True),
                migrate=True,
            )

            # Fleet session tokens
            self.db.define_table(
                "fleet_sessions",
                Field("killkrill_user_id", "integer"),
                Field("session_token", "string"),
                Field("fleet_jwt", "text"),
                Field("expires_at", "datetime"),
                Field("created_at", "datetime", default=datetime.utcnow),
                migrate=True,
            )

            self.db.commit()
        except Exception as e:
            print(f"Fleet SSO table setup: {e}")

    def create_fleet_user(
        self, killkrill_user: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a Fleet user for KillKrill user"""
        try:
            fleet_user_data = {
                "name": killkrill_user.get("first_name", "User"),
                "email": killkrill_user["email"],
                "password": secrets.token_urlsafe(32),  # Random password
                "global_role": "observer",  # Default role
                "admin_forced_password_reset": False,
            }

            headers = {"Authorization": f"Bearer {FLEET_API_TOKEN}"}
            response = requests.post(
                f"{FLEET_SERVER_URL}/api/v1/fleet/users",
                json=fleet_user_data,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 201:
                fleet_user = response.json()["user"]

                # Store mapping
                self.db.fleet_users.insert(
                    killkrill_user_id=killkrill_user["id"],
                    fleet_user_id=fleet_user["id"],
                    fleet_api_token="",  # Will be updated on login
                    is_active=True,
                )
                self.db.commit()

                return fleet_user
            else:
                print(f"Failed to create Fleet user: {response.text}")
                return None

        except Exception as e:
            print(f"Error creating Fleet user: {e}")
            return None

    def generate_fleet_jwt(self, killkrill_user_id: int) -> Optional[str]:
        """Generate JWT for Fleet authentication"""
        try:
            # Get or create Fleet user
            fleet_user_row = (
                self.db(self.db.fleet_users.killkrill_user_id == killkrill_user_id)
                .select()
                .first()
            )

            if not fleet_user_row:
                return None

            # Create JWT payload
            payload = {
                "user_id": fleet_user_row.fleet_user_id,
                "email": "",  # Will be populated by Fleet
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(hours=8),
                "iss": "killkrill-manager",
                "aud": "fleet-server",
            }

            # Generate JWT
            fleet_jwt = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

            # Store session
            session_token = secrets.token_urlsafe(32)
            self.db.fleet_sessions.insert(
                killkrill_user_id=killkrill_user_id,
                session_token=session_token,
                fleet_jwt=fleet_jwt,
                expires_at=payload["exp"],
            )
            self.db.commit()

            return fleet_jwt

        except Exception as e:
            print(f"Error generating Fleet JWT: {e}")
            return None


# Initialize Fleet SSO (will be done in main app)
fleet_sso = None


def get_fleet_sso(db):
    """Get Fleet SSO instance"""
    global fleet_sso
    if fleet_sso is None:
        fleet_sso = FleetSSO(db)
    return fleet_sso


@action("fleet")
@action("fleet/<path:path>")
def fleet_dashboard(path=None):
    """Embed Fleet dashboard with SSO"""
    # TODO: Implement proper authentication check
    # For now, assume user is authenticated

    fleet_url = FLEET_SERVER_URL
    if path:
        fleet_url += f"/{path}"

    # Generate SSO token for current user
    # fleet_jwt = get_fleet_sso(get_db()).generate_fleet_jwt(current_user_id)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>KillKrill - Fleet Management</title>
        <style>
            body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            .header {{ background: #1e293b; color: white; padding: 1rem; display: flex; justify-content: space-between; align-items: center; }}
            .nav {{ display: flex; gap: 2rem; }}
            .nav a {{ color: white; text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; }}
            .nav a:hover {{ background: #334155; }}
            .nav a.active {{ background: #3b82f6; }}
            .content {{ height: calc(100vh - 80px); }}
            .fleet-frame {{ width: 100%; height: 100%; border: none; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">
                <h2>🐧 KillKrill Management Portal</h2>
            </div>
            <nav class="nav">
                <a href="/manager">Dashboard</a>
                <a href="/manager/fleet" class="active">Fleet Management</a>
                <a href="/manager/grafana">Metrics</a>
                <a href="/manager/kibana">Logs</a>
                <a href="/manager/prometheus">Prometheus</a>
            </nav>
        </div>
        <div class="content">
            <iframe src="{fleet_url}" class="fleet-frame"
                    sandbox="allow-scripts allow-forms allow-same-origin allow-popups"></iframe>
        </div>
        <script>
            // Handle iframe authentication
            window.addEventListener('message', function(event) {{
                if (event.origin !== '{FLEET_SERVER_URL}') return;

                // Handle Fleet authentication requests
                if (event.data.type === 'fleet-auth-required') {{
                    // Send SSO token to Fleet
                    event.source.postMessage({{
                        type: 'fleet-auth-token',
                        token: 'SSO_TOKEN_HERE'  // Replace with actual SSO token
                    }}, event.origin);
                }}
            }});
        </script>
    </body>
    </html>
    """


@action("fleet/api/<path:path>", method=["GET", "POST", "PUT", "DELETE"])
@action.uses(CORS())
def fleet_api_proxy(path=None):
    """Proxy Fleet API requests with authentication"""
    try:
        # TODO: Add proper authentication check

        method = request.method
        url = f"{FLEET_SERVER_URL}/api/v1/fleet/{path}"

        headers = {
            "Authorization": f"Bearer {FLEET_API_TOKEN}",
            "Content-Type": "application/json",
        }

        # Forward request to Fleet API
        if method == "GET":
            fleet_response = requests.get(
                url, headers=headers, params=request.query, timeout=30
            )
        elif method == "POST":
            fleet_response = requests.post(
                url, headers=headers, json=request.json, timeout=30
            )
        elif method == "PUT":
            fleet_response = requests.put(
                url, headers=headers, json=request.json, timeout=30
            )
        elif method == "DELETE":
            fleet_response = requests.delete(url, headers=headers, timeout=30)
        else:
            response.status = 405
            return {"error": "Method not allowed"}

        # Return Fleet API response
        response.status = fleet_response.status_code
        response.headers["Content-Type"] = "application/json"

        try:
            return fleet_response.json()
        except:
            return {"data": fleet_response.text}

    except Exception as e:
        response.status = 500
        return {"error": f"Fleet API proxy error: {str(e)}"}


@action("fleet/hosts")
def fleet_hosts():
    """Fleet hosts management page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fleet Hosts - KillKrill</title>
        <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; }
            .host-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
            .host-card.online { border-left: 4px solid #10b981; }
            .host-card.offline { border-left: 4px solid #ef4444; }
            .host-header { display: flex; justify-content: space-between; align-items: center; }
            .status { padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 500; }
            .status.online { background: #d1fae5; color: #065f46; }
            .status.offline { background: #fee2e2; color: #991b1b; }
        </style>
    </head>
    <body>
        <div id="app">
            <h1>Fleet Host Management</h1>
            <div v-for="host in hosts" :key="host.id" :class="['host-card', host.status]">
                <div class="host-header">
                    <h3>{{ host.display_name }}</h3>
                    <span :class="['status', host.status]">{{ host.status }}</span>
                </div>
                <p><strong>Platform:</strong> {{ host.platform }}</p>
                <p><strong>Last Seen:</strong> {{ formatDate(host.seen_time) }}</p>
                <p><strong>Osquery Version:</strong> {{ host.osquery_version }}</p>
            </div>
        </div>

        <script>
        const {{ createApp }} = Vue;

        createApp({{
            data() {{
                return {{
                    hosts: []
                }};
            }},
            methods: {{
                async fetchHosts() {{
                    try {{
                        const response = await fetch('/manager/fleet/api/hosts');
                        const data = await response.json();
                        this.hosts = data.hosts || [];
                    }} catch (error) {{
                        console.error('Error fetching hosts:', error);
                    }}
                }},
                formatDate(dateString) {{
                    return new Date(dateString).toLocaleString();
                }}
            }},
            mounted() {{
                this.fetchHosts();
                // Refresh every 30 seconds
                setInterval(this.fetchHosts, 30000);
            }}
        }}).mount('#app');
        </script>
    </body>
    </html>
    """
