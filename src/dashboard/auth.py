"""
src/dashboard/auth.py
Provides HTTP Basic Auth for Developer Mode routes.
"""

from functools import wraps
from flask import request, current_app, Response

def check_auth(username, password):
    """Check if a username/password combination is valid."""
    cfg = current_app.config.get("SHM_CONFIG")
    dev_password = cfg.dashboard.developer_password if cfg else "CHANGE_ME"
    
    # Do not allow access if the deployment credential hasn't been securely set
    if dev_password in ("admin", "CHANGE_ME"):
        return False
        
    return username == 'admin' and password == dev_password

def authenticate():
    """Sends a 401 response that enables basic auth."""
    return Response(
        'Developer Mode Access Required.\n'
        'Please login with "admin" and the developer password.', 401,
        {'WWW-Authenticate': 'Basic realm="Developer Mode"'}
    )

def dev_required(f):
    """Decorator to require Developer Mode authentication for a route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
