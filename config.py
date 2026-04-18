import os

class Config:
    basedir = os.path.abspath(os.path.dirname(__file__))
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        # Generate once and save to file
        key_file = os.path.join(basedir, '.secret_key')
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                SECRET_KEY = f.read()
        else:
            SECRET_KEY = os.urandom(32)
            with open(key_file, 'wb') as f:
                f.write(SECRET_KEY)

    # Use PostgreSQL on Hugging Face, SQLite locally
    if os.environ.get("DATABASE_URL"):
        SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'tomatoguard.db')}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(basedir, "static", "uploads")

    SENSOR_API_KEY = os.environ.get("SENSOR_API_KEY")

    AI_CURE_ENABLED = os.environ.get("AI_CURE_ENABLED", "0").lower() in (
        "1", "true", "yes", "on"
    )

    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT = "1000 per hour;100 per minute"