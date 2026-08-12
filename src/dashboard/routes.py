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

    flattened = [temp for row in grid for temp in row]
    min_temp = min(flattened) if flattened else None
    max_temp = max(flattened) if flattened else None
    avg_temp = sum(flattened) / len(flattened) if flattened else None

    return jsonify({
        "grid": grid,
        "status": "ok",
        "min_temp_c": min_temp,
        "max_temp_c": max_temp,
        "avg_temp_c": avg_temp,
    })


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


# --- Alert Recipients Management --------------------------------

@dashboard_bp.route('/api/recipients', methods=['GET'])
def get_recipients():
    """Return list of all alert recipients (enabled and disabled)."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Repository unavailable"}), 503
    recipients = repo.get_all_recipients()
    return jsonify({"status": "success", "recipients": recipients})


@dashboard_bp.route('/api/recipients', methods=['POST'])
def add_recipient():
    """Add a new alert recipient."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Repository unavailable"}), 503
    
    data = request.json or {}
    phone_number = data.get("phone_number", "").strip()
    
    if not phone_number:
        return jsonify({"status": "error", "message": "Phone number required"}), 400
    
    try:
        recipient_id = repo.add_recipient(phone_number)
        return jsonify({
            "status": "success",
            "message": f"Recipient added: {phone_number}",
            "recipient_id": recipient_id
        }), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@dashboard_bp.route('/api/recipients/<int:recipient_id>', methods=['DELETE'])
def remove_recipient(recipient_id: int):
    """Remove an alert recipient."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Repository unavailable"}), 503
    
    try:
        repo.remove_recipient(recipient_id)
        return jsonify({"status": "success", "message": "Recipient removed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@dashboard_bp.route('/api/recipients/<int:recipient_id>/toggle', methods=['PATCH'])
def toggle_recipient(recipient_id: int):
    """Enable or disable a recipient."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Repository unavailable"}), 503
    
    data = request.json or {}
    enabled = data.get("enabled", True)
    
    try:
        repo.toggle_recipient(recipient_id, enabled)
        status_str = "enabled" if enabled else "disabled"
        return jsonify({
            "status": "success",
            "message": f"Recipient {status_str}",
            "recipient_id": recipient_id,
            "enabled": enabled
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# --- Alert Configuration Management -----

@dashboard_bp.route('/api/alert_config', methods=['GET'])
def get_alert_config():
    """Return current alert engine configuration."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Repository unavailable"}), 503
    
    try:
        config = repo.get_herd_risk_engine_config()
        return jsonify({
            "status": "success",
            "config": config
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@dashboard_bp.route('/api/alert_config', methods=['PATCH'])
def update_alert_config():
    """Update alert engine configuration."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Repository unavailable"}), 503
    
    data = request.json or {}
    
    # Validate configuration parameters
    valid_keys = {
        "stationary_alert_minutes", "stationary_heat_stress_minutes",
        "fever_delta_threshold_c", "population_lethargy_ratio",
        "population_persist_seconds", "thi_heat_stress_threshold",
        "cooldown_minutes", "alert_individual_enabled", "alert_population_enabled"
    }
    
    invalid_keys = set(data.keys()) - valid_keys
    if invalid_keys:
        return jsonify({
            "status": "error",
            "message": f"Invalid configuration keys: {', '.join(invalid_keys)}"
        }), 400
    
    # Type validation and conversion
    type_map = {
        "stationary_alert_minutes": float,
        "stationary_heat_stress_minutes": float,
        "fever_delta_threshold_c": float,
        "population_lethargy_ratio": float,
        "population_persist_seconds": int,
        "thi_heat_stress_threshold": float,
        "cooldown_minutes": int,
        "alert_individual_enabled": bool,
        "alert_population_enabled": bool,
    }
    
    try:
        # Convert and validate types
        validated_data = {}
        for key, value in data.items():
            expected_type = type_map[key]
            if expected_type == bool:
                validated_data[key] = value in (True, 1, "1", "true", "yes")
            else:
                validated_data[key] = expected_type(value)
        
        # Validate ranges
        if "stationary_alert_minutes" in validated_data and validated_data["stationary_alert_minutes"] <= 0:
            return jsonify({"status": "error", "message": "stationary_alert_minutes must be > 0"}), 400
        if "fever_delta_threshold_c" in validated_data and validated_data["fever_delta_threshold_c"] < 0:
            return jsonify({"status": "error", "message": "fever_delta_threshold_c must be >= 0"}), 400
        if "population_lethargy_ratio" in validated_data:
            if not (0 < validated_data["population_lethargy_ratio"] <= 1):
                return jsonify({"status": "error", "message": "population_lethargy_ratio must be between 0 and 1"}), 400
        if "cooldown_minutes" in validated_data and validated_data["cooldown_minutes"] <= 0:
            return jsonify({"status": "error", "message": "cooldown_minutes must be > 0"}), 400
        
        # Save to database
        repo = current_app.config.get("SHM_REPO")
        if not repo:
            return jsonify({"status": "error", "message": "Database unavailable"}), 503
        
        repo.set_herd_risk_engine_config(validated_data)
        updated_config = repo.get_herd_risk_engine_config()
        
        return jsonify({
            "status": "success",
            "message": "Alert configuration updated",
            "config": updated_config
        })
    
    except (ValueError, TypeError) as e:
        return jsonify({"status": "error", "message": f"Invalid data type: {str(e)}"}), 400


# ─── SMS MESSAGE TEMPLATES ──────────────────────────────────────────────────

@dashboard_bp.route('/api/sms_templates', methods=['GET'])
def get_sms_templates():
    """Get all SMS message templates."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    alert_type = request.args.get("alert_type")
    templates = repo.get_sms_templates(alert_type)
    return jsonify({"status": "success", "templates": templates})


@dashboard_bp.route('/api/sms_templates', methods=['POST'])
def create_sms_template():
    """Create a new SMS message template."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    data = request.get_json()
    alert_type = data.get("alert_type")
    name = data.get("name")
    message_body = data.get("message_body")
    
    if not alert_type or not name or not message_body:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
    
    try:
        template_id = repo.create_sms_template(alert_type, name, message_body)
        return jsonify({
            "status": "success",
            "message": "Template created",
            "template_id": template_id
        }), 201
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to create template: {str(e)}"}), 400


@dashboard_bp.route('/api/sms_templates/<int:template_id>', methods=['PATCH'])
def update_sms_template(template_id):
    """Update an SMS message template."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    data = request.get_json()
    message_body = data.get("message_body")
    enabled = data.get("enabled")
    
    if not message_body:
        return jsonify({"status": "error", "message": "message_body required"}), 400
    
    try:
        repo.update_sms_template(template_id, message_body, enabled)
        return jsonify({"status": "success", "message": "Template updated"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to update template: {str(e)}"}), 400


@dashboard_bp.route('/api/sms_templates/<int:template_id>', methods=['DELETE'])
def delete_sms_template(template_id):
    """Delete an SMS message template."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    try:
        repo.delete_sms_template(template_id)
        return jsonify({"status": "success", "message": "Template deleted"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to delete template: {str(e)}"}), 400


# ─── SMS MESSAGE LOGS ───────────────────────────────────────────────────────

@dashboard_bp.route('/api/sms_logs', methods=['GET'])
def get_sms_logs():
    """Get SMS message logs with optional date filtering."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    date_str = request.args.get("date")  # YYYY-MM-DD format
    alert_type = request.args.get("alert_type")
    
    if date_str:
        logs = repo.get_sms_logs_by_date(date_str)
    else:
        days_back = request.args.get("days", default=7, type=int)
        logs = repo.get_sms_logs(days_back, alert_type)
    
    return jsonify({"status": "success", "logs": logs})


@dashboard_bp.route('/api/sms_logs/dates', methods=['GET'])
def get_sms_log_dates():
    """Get all unique dates that have SMS logs."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    dates = repo.get_sms_log_dates()
    return jsonify({"status": "success", "dates": dates})


@dashboard_bp.route('/api/sms_logs/delete', methods=['POST'])
def delete_sms_logs():
    """Delete SMS logs before a specific date."""
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    data = request.get_json()
    before_date = data.get("before_date")  # YYYY-MM-DD format
    
    if not before_date:
        return jsonify({"status": "error", "message": "before_date required"}), 400
    
    try:
        deleted_count = repo.delete_sms_logs_before(before_date)
        return jsonify({
            "status": "success",
            "message": f"Deleted {deleted_count} SMS log entries"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to delete logs: {str(e)}"}), 400


# ─── SYSTEM TIME SYNC ───────────────────────────────────────────────────────

@dashboard_bp.route('/api/time_sync', methods=['GET'])
def get_system_time():
    """Get current system time and recent sync logs."""
    from datetime import datetime
    
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    current_time = datetime.utcnow().isoformat()
    sync_logs = repo.get_time_sync_logs(limit=10)
    
    return jsonify({
        "status": "success",
        "current_time": current_time,
        "sync_logs": sync_logs
    })


@dashboard_bp.route('/api/time_sync', methods=['POST'])
def sync_system_time():
    """Synchronize system time (from NTP or manual)."""
    import subprocess
    from datetime import datetime
    
    repo = current_app.config.get("SHM_REPO")
    if not repo:
        return jsonify({"status": "error", "message": "Database unavailable"}), 503
    
    data = request.get_json()
    source_type = data.get("source_type", "ntp")  # 'ntp', 'manual', or 'phone'
    new_time_str = data.get("new_time")  # ISO 8601 format
    
    old_time = datetime.utcnow().isoformat()
    
    try:
        if source_type == "manual" and new_time_str:
            # Manual time setting (on Raspberry Pi with timedatectl)
            result = subprocess.run(
                ["timedatectl", "set-time", new_time_str],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                repo.log_time_sync("manual", old_time, new_time_str, "failed", None, error_msg)
                return jsonify({"status": "error", "message": "Failed to set time"}), 400
        
        elif source_type == "ntp":
            # NTP sync (requires systemd-timesyncd)
            result = subprocess.run(
                ["timedatectl", "set-ntp", "true"],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                repo.log_time_sync("ntp", old_time, "", "failed", None, error_msg)
                return jsonify({"status": "error", "message": "NTP sync failed"}), 400
        
        new_time = datetime.utcnow().isoformat()
        repo.log_time_sync(source_type, old_time, new_time, "success", data.get("source_ip"))
        
        return jsonify({
            "status": "success",
            "message": f"Time synchronized ({source_type})",
            "old_time": old_time,
            "new_time": new_time
        })
    
    except subprocess.TimeoutExpired:
        repo.log_time_sync(source_type, old_time, "", "failed", None, "Timeout")
        return jsonify({"status": "error", "message": "Time sync timeout"}), 408
    except Exception as e:
        repo.log_time_sync(source_type, old_time, "", "failed", None, str(e))
        return jsonify({"status": "error", "message": f"Time sync error: {str(e)}"}), 400


@dashboard_bp.route('/api/alert_config/defaults', methods=['GET'])
def get_alert_config_defaults():
    """Return default alert configuration values."""
    defaults = {
        "stationary_alert_minutes": 15.0,
        "stationary_heat_stress_minutes": 30.0,
        "fever_delta_threshold_c": 2.0,
        "population_lethargy_ratio": 0.60,
        "population_persist_seconds": 3,
        "thi_heat_stress_threshold": 78.0,
        "cooldown_minutes": 5,
        "alert_individual_enabled": True,
        "alert_population_enabled": True,
    }
    
    descriptions = {
        "stationary_alert_minutes": "Minutes before triggering individual sick pig alert",
        "stationary_heat_stress_minutes": "Extended alert time when THI > threshold (heat stress condition)",
        "fever_delta_threshold_c": "Temperature delta in °C to trigger fever alert",
        "population_lethargy_ratio": "Ratio of pigs stationary to trigger population alert (0-1)",
        "population_persist_seconds": "Duration for population alert persistence (seconds)",
        "thi_heat_stress_threshold": "Temperature Humidity Index heat stress threshold",
        "cooldown_minutes": "Minimum minutes between repeated alerts of same type",
        "alert_individual_enabled": "Enable/disable individual pig fever alerts",
        "alert_population_enabled": "Enable/disable population lethargy alerts",
    }
    
    return jsonify({
        "status": "success",
        "defaults": defaults,
        "descriptions": descriptions
    })


# --- AP Connection Info ─────────────────────────────────────────────────────

@dashboard_bp.route('/api/ap-info')
def ap_info():
    """Return the live AP configuration for the dashboard connection panel.

    Exposes SSID, password (in AP mode only), IP, and a WPA QR string
    so the frontend can render a scannable Wi-Fi QR code.
    """
    cfg = current_app.config.get("SHM_CONFIG")
    if not cfg or cfg.network.mode != "ap":
        return jsonify({"ap_active": False})

    ssid = cfg.network.ap.ssid
    password = cfg.network.ap.password
    ip = cfg.network.ap.ip

    # WPA QR string — standard format used by iOS/Android camera apps
    wifi_qr = f"WIFI:T:WPA;S:{ssid};P:{password};;"

    return jsonify({
        "ap_active": True,
        "ssid": ssid,
        "password": password,
        "ip": ip,
        "wifi_qr": wifi_qr,
        "dashboard_url": f"http://{ip}:5000"
    })

