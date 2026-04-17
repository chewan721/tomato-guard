from dotenv import load_dotenv
load_dotenv()

import os
from flask import Flask, redirect, render_template, url_for
from sqlalchemy import inspect, text

from extensions import db, login_manager, csrf, limiter
from config import Config
from model import User

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)
login_manager.init_app(app)
csrf.init_app(app)
limiter.init_app(app)

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "error"

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.disease import disease_bp
from routes.cost import cost_bp
from routes.sensor import sensor_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(disease_bp)
app.register_blueprint(cost_bp)
app.register_blueprint(sensor_bp)

@app.route("/")
def index():
    return redirect(url_for("auth.login"))

@app.after_request
def apply_security_headers(response):
    if "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7860)), debug=debug)
