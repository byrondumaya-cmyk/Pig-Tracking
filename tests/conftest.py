import os
import threading
import time
import pytest
from src.dashboard.app import create_app
from src.config_loader import load_config
import sqlite3

@pytest.fixture(scope="session")
def flask_server():
    """Start Flask server in a background thread for Playwright tests."""
    # Ensure config path is set properly for test env
    if not os.path.exists("config/config.yaml"):
        # We need a minimal config to run
        pass
        
    cfg = load_config()
    
    # Init test DB if missing
    if not os.path.exists(cfg.database.path):
        os.makedirs(os.path.dirname(cfg.database.path), exist_ok=True)
        # minimal schema
        from src.database.schema import init_db
        init_db(cfg.database.path)

    app = create_app(cfg)
    # Set known password for tests
    app.config["SHM_CONFIG"].dashboard.developer_password = "pigtracking123"
    
    # Start server
    def run_server():
        # Disable reloader and threading to avoid issues in background thread
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Wait for server to boot
    time.sleep(2)
    
    yield "http://127.0.0.1:5000"
