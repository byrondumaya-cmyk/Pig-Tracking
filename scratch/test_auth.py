import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from src.dashboard.routes import dashboard_bp
from src.config_loader import AppConfig, DashboardConfig

app = Flask(__name__)
app.register_blueprint(dashboard_bp)

# Mock config
class MockConfig(AppConfig):
    dashboard = DashboardConfig(developer_password="CHANGE_ME")

app.config["SHM_CONFIG"] = MockConfig()

def test_auth():
    with app.test_client() as client:
        # Normal user accessing index
        res = client.get("/")
        assert res.status_code == 200, "Normal users should access /"
        
        # Unauthenticated user accessing /settings
        res = client.get("/settings")
        assert res.status_code == 401, "Normal users should NOT access /settings"
        
        # User trying the default "admin" password (should fail because dev_password is CHANGE_ME or admin)
        res = client.get("/settings", auth=("admin", "admin"))
        assert res.status_code == 401, "Default admin password should be blocked"
        
        res = client.get("/settings", auth=("admin", "CHANGE_ME"))
        assert res.status_code == 401, "CHANGE_ME password should be blocked"

        # Now set a valid password
        app.config["SHM_CONFIG"].dashboard.developer_password = "secure_password"
        
        # Bad password
        res = client.get("/settings", auth=("admin", "wrong"))
        assert res.status_code == 401, "Wrong password should be blocked"
        
        # Good password
        res = client.get("/settings", auth=("admin", "secure_password"))
        # we expect a 500 or 200 depending on if template exists, but NOT a 401
        assert res.status_code != 401, "Good password should authenticate"
        
        # Check backend endpoint directly
        res = client.post("/api/dev/gsm_test")
        assert res.status_code == 401, "Backend endpoints must be protected"
        
        res = client.post("/api/dev/gsm_test", auth=("admin", "secure_password"))
        assert res.status_code != 401, "Authenticated dev can access backend"

    print("All auth tests passed!")

if __name__ == "__main__":
    test_auth()
