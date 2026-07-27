"""
src/dashboard/routes.py
Flask Dashboard API Routes

PURPOSE:
    Provides HTTP endpoints for the web dashboard.
    Serves HTML pages and JSON endpoints for AJAX polling.
"""

import json
from flask import Blueprint, render_template, jsonify, request, current_app, Response
from src.config_loader import load_config
import yaml
from pathlib import Path

# Create a blueprint for dashboard routes
dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')

@dashboard_bp.route('/')
def index():
    """Main Dashboard: Side-by-Side view + Alert Log."""
    return render_template('index.html')

@dashboard_bp.route('/video_feed')
def video_feed():
    """MJPEG live camera stream endpoint."""
    from src.dashboard.stream import generate_mjpeg
    cfg = current_app.config.get("SHM_CONFIG")
    quality = cfg.dashboard.stream_jpeg_quality if cfg else 70
    return Response(generate_mjpeg(quality), mimetype='multipart/x-mixed-replace; boundary=frame')

@dashboard_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings Panel: Edit GSM numbers and risk thresholds live."""
    if request.method == 'POST':
        try:
            cfg_path = Path("config/config.yaml")
            with open(cfg_path, "r") as f:
                config = yaml.safe_load(f)

            data = request.json
            if 'gsm' in data:
                if 'phone_numbers' in data['gsm']:
                    config['gsm']['phone_numbers'] = data['gsm']['phone_numbers']
                if 'cooldown_minutes' in data['gsm']:
                    config['gsm']['cooldown_minutes'] = int(data['gsm']['cooldown_minutes'])
            if 'health' in data:
                h = data['health']
                for key in ('stationary_alert_minutes', 'fever_delta_threshold_c', 'population_lethargy_ratio'):
                    if key in h:
                        config['health'][key] = float(h[key])

            with open(cfg_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

            return jsonify({"status": "success", "message": "Settings saved. Changes take effect on next restart."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    cfg_path = Path("config/config.yaml")
    with open(cfg_path, "r") as f:
        config = yaml.safe_load(f)
    return render_template('settings.html', config=config)

# --- AJAX Polling Endpoints ---------------------------------

@dashboard_bp.route('/api/thermal_feed')
def thermal_feed():
    """Returns the current 8x8 AMG8833 thermal grid."""
    # TODO: Connect to active global thermal state
    # Returning dummy data for UI scaffolding
    dummy_grid = [[30.0 + (i+j)*0.5 for j in range(8)] for i in range(8)]
    return jsonify({"grid": dummy_grid})

@dashboard_bp.route('/api/ambient')
def ambient_feed():
    """Returns the latest DHT22 reading from the database."""
    repo = current_app.config.get("SHM_REPO")
    if repo:
        row = repo.get_latest_ambient()
        if row:
            thi = row.get('thi', 0.0)
            return jsonify({
                "temp_c": row.get('temp_c'),
                "humidity_pct": row.get('humidity_pct'),
                "thi": thi,
                "is_heat_stress": thi > 78.0
            })
    return jsonify({"temp_c": None, "humidity_pct": None, "thi": None, "is_heat_stress": False})

@dashboard_bp.route('/api/pen_alerts')
def pen_alerts():
    """Returns recent alert logs from the database."""
    repo = current_app.config.get("SHM_REPO")
    if repo:
        rows = repo.get_recent_alerts(limit=20)
        alerts = [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "alert_type": r["alert_type"],
                "message": f"{r['trigger_reason']} | Zone:{r.get('pig_zone_temp_c') or '-'}°C | THI:{r.get('ambient_thi', '-'):.1f}" if r.get('ambient_thi') else r.get('trigger_reason', ''),
                "resolved": bool(r["resolved"]),
                "sms_sent": bool(r.get("sms_sent", False)),
            }
            for r in rows
        ]
        return jsonify({"alerts": alerts, "has_unresolved": repo.has_unresolved_alerts()})
    return jsonify({"alerts": [], "has_unresolved": False})

@dashboard_bp.route('/api/behavior_counts')
def behavior_counts():
    """Returns current active behaviors in frame."""
    # TODO: Connect to active BehaviorAnalyzer state
    return jsonify({
        "lying": 3,
        "sitting": 1,
        "walking": 2,
        "feeding": 1,
        "total": 7
    })
