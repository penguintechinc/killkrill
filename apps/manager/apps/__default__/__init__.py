"""
KillKrill Manager - Default App
Redirects root requests to the manager interface
"""

from py4web import action, redirect


@action("index")
def index():
    """Redirect root to manager interface"""
    redirect("/manager/")


@action("healthz")
def healthz():
    """Redirect health check to manager"""
    redirect("/manager/healthz")
