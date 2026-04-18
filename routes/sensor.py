from dotenv.main import logger
from flask import Blueprint, request, jsonify, current_app, session
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from extensions import csrf, limiter
from model import SensorData, SensorProfile, UserSensorData, NotificationLog, db, generate_device_token
from model import _nepal_now
import secrets
import time

sensor_bp = Blueprint("sensor", __name__)


# Validation helper
def _first_present(data: dict, keys: list[str]):
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _extract_payload():
    """Accept JSON first, then form payloads commonly sent by ESP clients."""
    json_data = request.get_json(silent=True)
    if isinstance(json_data, dict):
        return json_data

    if request.form:
        return request.form.to_dict(flat=True)

    return {}


def validate_sensor_data(data: dict):
    """Returns (ok, error_message)."""
    try:
        temp_raw = _first_present(data, ["temperature", "temp", "t"])
        humidity_raw = _first_present(data, ["humidity", "hum", "h"])
        soil_raw = _first_present(data, ["soil", "soil_moisture", "moisture", "m"])

        temp = float(temp_raw)
        humidity = float(humidity_raw)
        soil = float(soil_raw)
    except (TypeError, ValueError, KeyError) as exc:
        return False, f"Invalid or missing field: {exc}"

    if not (-50 <= temp <= 60):
        return False, "Temperature out of valid range (–50 to 60 °C)."
    if not (0 <= humidity <= 100):
        return False, "Humidity must be between 0–100 %."
    if not (0 <= soil <= 100):
        return False, "Soil moisture must be between 0–100 %."

    return True, {"temperature": temp, "humidity": humidity, "soil": soil}


def _extract_chip_id(payload: dict):
    chip_raw = (
        payload.get("chip_id")
        or payload.get("esp_id")
        or request.headers.get("X-ESP-Chip-ID")
        or request.args.get("chip_id")
    )
    if chip_raw is None:
        return None
    return str(chip_raw).strip().upper()


def _extract_api_key(payload: dict):
    auth_header = request.headers.get("Authorization", "")
    bearer_token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None
    return (
        request.headers.get("X-API-Key")
        or bearer_token
        or payload.get("api_key")
        or request.args.get("api_key")
    )


# ========== DEVICE PAIRING ENDPOINTS ==========

@sensor_bp.route("/api/create-pairing-token", methods=["POST"])
@login_required
def create_pairing_token():
    """Create a temporary pairing token for a new device"""
    pairing_token = secrets.token_urlsafe(32)
    
    # Store in session (for demo) - in production use a database table
    session['pairing_token'] = pairing_token
    session['pairing_expiry'] = time.time() + 600  # 10 minutes
    session['pairing_user_id'] = current_user.id
    
    return jsonify({
        "success": True,
        "token": pairing_token,
        "expires_in": 600
    })


@sensor_bp.route("/api/register-device", methods=["POST"])
def register_device():
    """Register a new ESP32 device using a pairing token"""
    data = request.get_json()
    pairing_token = data.get('pairing_token')
    chip_id = data.get('chip_id')
    device_name = data.get('device_name', 'ESP32')
    
    if not pairing_token or not chip_id:
        return jsonify({"error": "Missing pairing_token or chip_id"}), 400
    
    # Verify pairing token (check session - for demo)
    # In production, check against a database table
    stored_token = session.get('pairing_token')
    stored_expiry = session.get('pairing_expiry', 0)
    user_id = session.get('pairing_user_id')
    
    if not stored_token or stored_token != pairing_token or time.time() > stored_expiry:
        return jsonify({"error": "Invalid or expired pairing token"}), 401
    
    if not user_id:
        return jsonify({"error": "No user associated with pairing token"}), 401
    
    # Check if device already exists
    existing = SensorProfile.query.filter_by(chip_id=chip_id).first()
    if existing:
        return jsonify({"error": "Device already registered", "device_token": existing.device_token}), 409
    
    try:
        # Create new sensor profile for the user
        profile = SensorProfile(
            chip_id=chip_id,
            device_token=generate_device_token(),
            user_id=user_id,
            device_name=device_name
        )
        db.session.add(profile)
        db.session.commit()
        
        # Clear the used pairing token
        session.pop('pairing_token', None)
        session.pop('pairing_expiry', None)
        session.pop('pairing_user_id', None)
        
        return jsonify({
            "success": True,
            "device_token": profile.device_token,
            "chip_id": chip_id,
            "device_name": profile.device_name
        }), 200
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Device already paired or invalid"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ========== SENSOR DATA ENDPOINTS ==========

# POST /api/sensor — receives data from ESP32
@csrf.exempt
@sensor_bp.route("/api/sensor", methods=["POST"])
@limiter.limit("1000 per hour")
def receive_sensor_data():
    payload = _extract_payload()
    api_key = _extract_api_key(payload)
    chip_id = _extract_chip_id(payload)
    
    # Check if this is the global API key (new device, not yet paired)
    global_api_key = current_app.config.get("SENSOR_API_KEY")
    is_global_key = (api_key == global_api_key)
    
    # Try to find existing profile by device token
    profile = SensorProfile.query.filter_by(device_token=api_key).first()
    
    # If still no profile and not using global key, reject
    if profile is None and not is_global_key:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    if not payload:
        return jsonify({"status": "error", "message": "No JSON body received."}), 400
    
    ok, result = validate_sensor_data(payload)
    if not ok:
        return jsonify({"status": "error", "message": result}), 422
    
    # Save the reading
    if profile is not None:
        # User-scoped data
        device_name = str(payload.get("device_name") or profile.device_name or "ESP32").strip()[:100]
        reading = UserSensorData(
            user_id=profile.user_id,
            device_name=device_name,
            temperature=result["temperature"],
            humidity=result["humidity"],
            soil_moisture=result["soil"],
        )
        db.session.add(reading)
        db.session.commit()
        
        response = {
            "status": "success", 
            "saved": result,
            "user_id": profile.user_id,
            "device_name": device_name,
            "chip_id": profile.chip_id
        }
        return jsonify(response), 200
        
    elif is_global_key and chip_id:
        # Legacy mode - store in global SensorData table
        new_reading = SensorData(
            temperature=result["temperature"],
            humidity=result["humidity"],
            soil_moisture=result["soil"],
            chip_id=chip_id  
        )
        db.session.add(new_reading)
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "saved": result,
            "mode": "legacy_global_key",
            "message": "Data saved. To view in dashboard, pair this device with your account."
        }), 200
    else:
        return jsonify({"status": "error", "message": "No valid profile found"}), 400


@csrf.exempt
@sensor_bp.route("/api/sensor/ping", methods=["GET"])
@limiter.limit("1200 per hour")
def sensor_ping():
    payload = _extract_payload()
    api_key = _extract_api_key(payload)
    chip_id = _extract_chip_id(payload)
    profile = SensorProfile.query.filter_by(device_token=api_key).first()
    is_legacy_global_key = api_key == current_app.config.get("SENSOR_API_KEY")

    if profile is None and is_legacy_global_key and chip_id:
        profile = SensorProfile.query.filter_by(chip_id=chip_id).first()

    if profile is None and not is_legacy_global_key:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    if profile is not None:
        latest = (
            UserSensorData.query.filter_by(user_id=profile.user_id)
            .order_by(UserSensorData.timestamp.desc())
            .first()
        )
    else:
        latest = SensorData.query.order_by(SensorData.timestamp.desc()).first()

    latest_payload = None
    if latest:
        latest_payload = {
            "temperature": latest.temperature,
            "humidity": latest.humidity,
            "soil": latest.soil_moisture,
            "timestamp": latest.timestamp.isoformat(),
        }
        if profile is not None:
            latest_payload["device_name"] = latest.device_name

    return jsonify(
        {
            "status": "ok",
            "scope": "user" if profile is not None else "legacy_global",
            "latest": latest_payload,
        }
    ), 200


# GET /api/latest — latest reading for dashboard live cards
@sensor_bp.route("/api/latest")
@login_required
def latest_sensor():
    latest = (
        UserSensorData.query.filter_by(user_id=current_user.id)
        .order_by(UserSensorData.timestamp.desc())
        .first()
    )
    if latest:
        return jsonify(
            {
                "temperature": latest.temperature,
                "humidity": latest.humidity,
                "soil": latest.soil_moisture,
                "timestamp": latest.timestamp.isoformat(),
            }
        )
    return jsonify({"temperature": 0, "humidity": 0, "soil": 0, "timestamp": None})


# GET /api/history — daily aggregated data for dashboard
@sensor_bp.route("/api/history")
@login_required
def sensor_history():
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not start_date_str:
        start_date_str = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
    if not end_date_str:
        end_date_str = datetime.now().strftime('%Y-%m-%d')

    stats = db.session.query(
        func.date(UserSensorData.timestamp).label('day'),
        func.max(UserSensorData.temperature).label('max_temp'),
        func.min(UserSensorData.temperature).label('min_temp'),
        func.max(UserSensorData.humidity).label('max_hum'),
        func.min(UserSensorData.humidity).label('min_hum'),
        func.max(UserSensorData.soil_moisture).label('max_soil'),
        func.min(UserSensorData.soil_moisture).label('min_soil')
    ).filter(
        UserSensorData.user_id == current_user.id,
        func.date(UserSensorData.timestamp) >= start_date_str,
        func.date(UserSensorData.timestamp) <= end_date_str
    ).group_by(func.date(UserSensorData.timestamp)).order_by('day').all()

    results = {
        "days": [],
        "temperature": {"max": [], "min": []},
        "humidity": {"max": [], "min": []},
        "soil": {"max": [], "min": []}
    }

    for s in stats:
        results["days"].append(str(s.day))
        results["temperature"]["max"].append(round(s.max_temp, 1) if s.max_temp is not None else 0)
        results["temperature"]["min"].append(round(s.min_temp, 1) if s.min_temp is not None else 0)
        results["humidity"]["max"].append(round(s.max_hum, 1) if s.max_hum is not None else 0)
        results["humidity"]["min"].append(round(s.min_hum, 1) if s.min_hum is not None else 0)
        results["soil"]["max"].append(round(s.max_soil, 1) if s.max_soil is not None else 0)
        results["soil"]["min"].append(round(s.min_soil, 1) if s.min_soil is not None else 0)

    return jsonify(results)


@sensor_bp.route("/api/unpaired-devices")
@login_required
def unpaired_devices():
    """List devices that have sent data via global key but aren't paired"""
    unpaired_chips = db.session.query(SensorData.chip_id)\
        .filter(SensorData.chip_id.isnot(None))\
        .distinct()\
        .all()
    
    unpaired_chips = [c[0] for c in unpaired_chips]
    paired_chips = [p.chip_id for p in SensorProfile.query.filter(SensorProfile.chip_id.isnot(None)).all()]
    unpaired = [chip for chip in unpaired_chips if chip not in paired_chips]
    
    devices = []
    for chip in unpaired:
        latest = SensorData.query.filter_by(chip_id=chip)\
            .order_by(SensorData.timestamp.desc())\
            .first()
        if latest:
            devices.append({
                "chip_id": chip,
                "last_seen": latest.timestamp.isoformat(),
                "last_temperature": latest.temperature,
                "last_humidity": latest.humidity,
                "last_soil": latest.soil_moisture
            })
    return jsonify({"devices": devices}), 200


@sensor_bp.route("/api/pair-device", methods=["POST"])
@login_required
def pair_device():
    data = request.get_json()
    chip_id = data.get('chip_id')
    
    if not chip_id:
        return jsonify({"error": "No chip_id provided"}), 400
    
    try:
        profile = SensorProfile(
            chip_id=chip_id,
            device_token=generate_device_token(),
            user_id=current_user.id,
            device_name=data.get('device_name', f'ESP32-{chip_id[-6:]}')
        )
        db.session.add(profile)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Device already paired or invalid"}), 409
    
    legacy_readings = SensorData.query.filter_by(chip_id=chip_id).all()
    migrated_count = 0
    
    for reading in legacy_readings:
        new_reading = UserSensorData(
            user_id=current_user.id,
            device_name=profile.device_name,
            temperature=reading.temperature,
            humidity=reading.humidity,
            soil_moisture=reading.soil_moisture,
            timestamp=reading.timestamp
        )
        db.session.add(new_reading)
        migrated_count += 1
    
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": f"Device paired successfully. Migrated {migrated_count} historical readings.",
        "chip_id": chip_id,
        "device_name": profile.device_name
    }), 200


# ========== WATERING RECOMMENDATIONS ==========

@sensor_bp.route("/api/watering-recommendation")
@login_required
def watering_recommendation():
    latest = UserSensorData.query.filter_by(user_id=current_user.id)\
        .order_by(UserSensorData.timestamp.desc())\
        .first()
    
    if not latest:
        return jsonify({
            "has_data": False,
            "message": "No sensor data yet"
        }), 200
    
    soil_moisture = latest.soil_moisture
    recommendation = get_watering_advice(soil_moisture)
    should_notify = should_send_notification(current_user.id, soil_moisture, recommendation["action"])
    
    return jsonify({
        "has_data": True,
        "soil_moisture": soil_moisture,
        "temperature": latest.temperature,
        "humidity": latest.humidity,
        "recommendation": recommendation,
        "should_notify": should_notify,
        "timestamp": latest.timestamp.isoformat()
    }), 200


def get_watering_advice(soil_moisture):
    if soil_moisture < 30:
        return {
            "action": "water_urgent",
            "level": "critical",
            "message": "URGENT! Soil is extremely dry!",
            "advice": "Water immediately - soil is critically dry",
            "amount": "Water thoroughly (500ml-1L) until water drains from bottom",
            "icon": "🔴",
            "color": "#f44336"
        }
    elif soil_moisture < 50:
        return {
            "action": "water",
            "level": "warning",
            "message": "Time to water your plants!",
            "advice": "Soil is getting dry, needs watering",
            "amount": "Water moderately (200-300ml)",
            "icon": "💧",
            "color": "#ff9800"
        }
    elif soil_moisture < 60:
        return {
            "action": "borderline",
            "level": "info",
            "message": "Soil is slightly dry",
            "advice": "Consider watering soon if no rain expected",
            "amount": "Light watering (100-150ml) optional",
            "icon": "⚠️",
            "color": "#ffc107"
        }
    elif 60 <= soil_moisture <= 80:
        return {
            "action": "normal",
            "level": "good",
            "message": "Soil moisture is optimal!",
            "advice": "No watering needed",
            "amount": "None",
            "icon": "✅",
            "color": "#4caf50"
        }
    elif soil_moisture <= 90:
        return {
            "action": "reduce",
            "level": "warning",
            "message": "Soil is too wet!",
            "advice": "Reduce watering frequency",
            "amount": "Skip next watering session",
            "icon": "⚠️",
            "color": "#ff9800"
        }
    else:
        return {
            "action": "stop_urgent",
            "level": "critical",
            "message": "URGENT! Soil is waterlogged!",
            "advice": "Stop watering immediately! Check drainage",
            "amount": "No water until soil dries (24-48 hours)",
            "icon": "🔴",
            "color": "#f44336"
        }


def should_send_notification(user_id, soil_moisture, action):
    if action in ["normal", "borderline"]:
        return False
    
    last_notification = NotificationLog.query.filter_by(
        user_id=user_id,
        action_type=action
    ).order_by(NotificationLog.created_at.desc()).first()
    
    if not last_notification:
        return True
    
    time_since_last = _nepal_now() - last_notification.created_at
    return time_since_last > timedelta(hours=1)


@sensor_bp.route("/api/notification-log", methods=["POST"])
@login_required
def log_notification():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        notification = NotificationLog(
            user_id=current_user.id,
            action_type=data.get('action'),
            message=data.get('message'),
            soil_moisture=data.get('soil_moisture')
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error(f"Error logging notification: {e}")
        return jsonify({"error": str(e)}), 500