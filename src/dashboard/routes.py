"""
src/dashboard/routes.py
Flask Dashboard API Routes

PURPOSE:
    Provides HTTP endpoints for the web dashboard.
    Serves HTML pages and JSON endpoints for AJAX polling.
"""

import json
import os
import shutil
import time
from pathlib import Path

import yaml
from flask import Blueprint, Response, current_app, jsonify, render_template, request

from src.config_loader import CONFIG_PATH

# Create a blueprint for dashboard routes
dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')

# Startup time for uptime calculation
_START_TIME = time.time()


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
            # Use CONFIG_PATH constant — never a raw relative path
            with open(CONFIG_PATH, "r") as f:
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

            with open(CONFIG_PATH, "w") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

            return jsonify({"status": "success", "message": "Settings saved. Changes take effect on next restart."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return render_template('settings.html', config=config)


# --- AJAX Polling Endpoints ---------------------------------

@dashboard_bp.route('/api/thermal_feed')
def thermal_feed():
    """Returns the latest 8x8 AMG8833 thermal grid from the live ThermalBuffer."""
    from src.dashboard.stream import ThermalBuffer
    grid = ThermalBuffer.read()
    if grid is None:
        # Sensor not yet available or disabled — return null so UI can show offline state
        return jsonify({"grid": None, "status": "unavailable"})
    return jsonify({"grid": grid, "status": "ok"})


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
                "message": (
                    f"{r['trigger_reason']} | Zone:{r.get('pig_zone_temp_c') or '-'}°C "
                    f"| THI:{r.get('ambient_thi', 0.0):.1f}"
                    if r.get('ambient_thi') is not None
                    else r.get('trigger_reason', '')
                ),
                "resolved": bool(r["resolved"]),
                "sms_sent": bool(r.get("sms_sent", False)),
            }
            for r in rows
        ]
        return jsonify({"alerts": alerts, "has_unresolved": repo.has_unresolved_alerts()})
    return jsonify({"alerts": [], "has_unresolved": False})


@dashboard_bp.route('/api/behavior_counts')
def behavior_counts():
    """Returns current live behavior counts from the BehaviorBuffer."""
    from src.dashboard.stream import BehaviorBuffer
    data = BehaviorBuffer.read()
    # Always include all 8 canonical classes so the UI doesn't break on missing keys
    canonical = ["lying", "standing", "walking", "sitting", "feeding", "drinking",
                 "social_interaction", "aggression"]
    result = {cls: data.get(cls, 0) for cls in canonical}
    result["total"] = data.get("total", 0)
    return jsonify(result)


@dashboard_bp.route('/api/resolve_alert/<int:alert_id>', methods=['POST'])
def resolve_alert(alert_id: int):
    """
    Farmer confirms they have inspected the pen.
    Sets resolved=1. This is the ONLY correct way to resolve an alert.
    """
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Repository unavailable"}), 503
    repo.resolve_alert(alert_id)
    return jsonify({"status": "success", "alert_id": alert_id})


@dashboard_bp.route('/api/system_status')
def system_status():
    """
    Returns live system component status for field diagnostics without SSH.
    All checks are best-effort and non-blocking.
    """
    from src.dashboard.stream import FrameBuffer, ThermalBuffer

    # Camera: online if FrameBuffer has received at least one frame
    camera_status = "online" if FrameBuffer.read() is not None else "offline"

    # Thermal: online if ThermalBuffer has received at least one grid
    thermal_status = "online" if ThermalBuffer.read() is not None else "offline"

    # GSM: check config — actual connection test would need serial access
    cfg = current_app.config.get("SHM_CONFIG")
    gsm_status = "enabled" if (cfg and cfg.gsm.enabled) else "disabled"

    # Storage: disk usage of data directory
    try:
        usage = shutil.disk_usage(Path("."))
        used_pct = int(usage.used / usage.total * 100)
        storage_str = f"{used_pct}%"
    except Exception:
        storage_str = "unknown"

    # Uptime
    elapsed = int(time.time() - _START_TIME)
    hours, remainder = divmod(elapsed, 3600)
    minutes = remainder // 60
    uptime_str = f"{hours}h{minutes:02d}m"

    # AI model name from config
    model_name = "YOLOv8n (ONNX)"
    if cfg:
        model_path = Path(cfg.inference.model_path)
        model_name = f"YOLOv8n ({model_path.name})"

    return jsonify({
        "camera": camera_status,
        "thermal": thermal_status,
        "gsm": gsm_status,
        "network_mode": cfg.network.mode if cfg else "unknown",
        "ap_ssid": cfg.network.ap.ssid if cfg else None,
        "ap_ip": cfg.network.ap.ip if cfg else None,
        "storage": storage_str,
        "uptime": uptime_str,
        "ai_model": model_name,
    })
