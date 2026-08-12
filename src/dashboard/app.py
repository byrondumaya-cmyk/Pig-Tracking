"""
src/dashboard/app.py
Flask Application Factory

PURPOSE:
    Creates and configures the Flask dashboard app.
    Registers blueprints, injects shared state (config, repository, frame buffer).
    Must be called in a daemon thread from main.py.
"""

from __future__ import annotations

import logging

from flask import Flask

logger = logging.getLogger(__name__)


def create_app(cfg, repository=None) -> Flask:
    """
    Flask application factory.

    Args:
        cfg: AppConfig object from config_loader.
        repository: SwineRepository instance for database access.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Attach config and repo to app context so routes can access them
    app.config["SHM_CONFIG"] = cfg
    app.config["SHM_REPO"] = repository

    # Register blueprints
    from src.dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    logger.info("Flask dashboard app created.")
    return app
