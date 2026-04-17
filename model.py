from extensions import db
from flask_login import UserMixin
from datetime import datetime
from zoneinfo import ZoneInfo
import secrets

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")

def _nepal_now():
    return datetime.now(NEPAL_TZ)

def generate_device_token() -> str:
    return secrets.token_urlsafe(32)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    disease_history = db.relationship(
        "DiseaseHistory", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    sensor_profile = db.relationship(
        "SensorProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    sensor_readings = db.relationship(
        "UserSensorData", backref="user", lazy=True, cascade="all, delete-orphan"
    )

class SensorData(db.Model):
    __tablename__ = "sensor_data"

    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    soil_moisture = db.Column(db.Float, nullable=False)
    chip_id = db.Column(db.String(32), nullable=True)
    timestamp = db.Column(db.DateTime, default=_nepal_now)

    def __repr__(self):
        return f"<SensorData {self.timestamp}: T={self.temperature}, H={self.humidity}, S={self.soil_moisture}>"

class SensorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    device_name = db.Column(db.String(100), nullable=False, default="ESP32")
    chip_id = db.Column(db.String(32), nullable=True, unique=True, index=True)
    wifi_ssid = db.Column(db.String(100), nullable=True)
    device_token = db.Column(db.String(120), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=_nepal_now)
    updated_at = db.Column(db.DateTime, default=_nepal_now, onupdate=_nepal_now)

class UserSensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    device_name = db.Column(db.String(100), nullable=True)
    soil_moisture = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=_nepal_now)

class DiseaseHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    disease_name = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    image_filename = db.Column(db.String(200), nullable=False)       # stored UUID name
    original_filename = db.Column(db.String(200), nullable=True)     # user's original filename
    timestamp = db.Column(db.DateTime, default=_nepal_now)
    
class NotificationLog(db.Model):
    __tablename__ = "notification_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action_type = db.Column(db.String(50))
    message = db.Column(db.Text)
    soil_moisture = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=_nepal_now)

    user = db.relationship("User", backref="notifications")