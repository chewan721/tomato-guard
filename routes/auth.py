import re
from urllib.parse import urlparse, urljoin
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from model import User, SensorProfile, generate_device_token, db

auth_bp = Blueprint("auth", __name__)

def _is_safe_redirect(target: str) -> bool:
    """Return True only if target is a relative path on this host."""
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_username(username: str):
    """Returns (ok, error_message)."""
    if len(username) < 3 or len(username) > 50:
        return False, "Username must be 3–50 characters."
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username may only contain letters, numbers and underscores."
    return True, None


def validate_password(password: str):
    """Returns (ok, error_message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    return True, None


# Register
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard_bp.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        # Do NOT strip passwords — leading/trailing spaces are valid
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        ok, err = validate_username(username)
        if not ok:
            flash(err, "error")
            return render_template("register.html")

        if not validate_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        ok, err = validate_password(password)
        if not ok:
            flash(err, "error")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("register.html")

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method="scrypt"),
        )
        db.session.add(new_user)
        db.session.flush()

        profile = SensorProfile(
            user_id=new_user.id,
            device_name=f"{new_user.username}-esp32",
            device_token=generate_device_token(),
        )
        db.session.add(profile)
        db.session.commit()

        login_user(new_user)
        flash("Account created! Welcome to TomatoGuard.", "success")
        return redirect(url_for("dashboard_bp.dashboard"))

    return render_template("register.html")


# Login
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard_bp.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        # Do NOT strip passwords
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        login_user(user)
        flash("Logged in successfully.", "success")

        next_page = request.args.get("next")
        if next_page and _is_safe_redirect(next_page):
            return redirect(next_page)
        return redirect(url_for("dashboard_bp.dashboard"))

    return render_template("login.html")


# Logout
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# Account settings
@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    profile = SensorProfile.query.filter_by(user_id=current_user.id).first()
    if profile is None:
        profile = SensorProfile(
            user_id=current_user.id,
            device_name=f"{current_user.username}-esp32",
            device_token=generate_device_token(),
        )
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        action = request.form.get("action", "account_save")

        if action == "esp_regenerate_token":
            profile.device_token = generate_device_token()
            db.session.commit()
            flash("ESP device token regenerated.", "success")
            return redirect(url_for("auth.account"))

        if action == "esp_save":
            device_name = request.form.get("device_name", "").strip()
            wifi_ssid = request.form.get("wifi_ssid", "").strip()
            chip_id_raw = request.form.get("chip_id")
            chip_id = chip_id_raw.strip().upper() if chip_id_raw is not None else None

            if not device_name:
                flash("Device name is required.", "error")
                return render_template("account.html", sensor_profile=profile)

            if len(device_name) > 100:
                flash("Device name must be 100 characters or fewer.", "error")
                return render_template("account.html", sensor_profile=profile)

            if chip_id is not None and chip_id and (len(chip_id) < 8 or len(chip_id) > 32):
                flash("ESP Chip ID must be 8 to 32 characters.", "error")
                return render_template("account.html", sensor_profile=profile)

            existing_chip = None
            if chip_id is not None and chip_id:
                existing_chip = SensorProfile.query.filter(
                    SensorProfile.chip_id == chip_id,
                    SensorProfile.user_id != current_user.id,
                ).first()
            if existing_chip:
                flash("This ESP Chip ID is already linked to another account.", "error")
                return render_template("account.html", sensor_profile=profile)

            profile.device_name = device_name
            profile.wifi_ssid = wifi_ssid or None
            if chip_id is not None:
                profile.chip_id = chip_id or None

            try:
                # Even though we checked if the chip_id exists above,
                # another request could have committed the same chip_id in the
                # millisecond between our check and this commit (a Race Condition).
                # Since the model has a unique=True constraint, the DB will raise
                # an IntegrityError. If we don't catch it, the user sees a 500.
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("This ESP Chip ID was just linked by another user. Please verify your ID.", "error")
                return render_template("account.html", sensor_profile=profile)

            flash("ESP settings updated.", "success")
            return redirect(url_for("auth.account"))

        # Every render_template("account.html") below MUST include
        # sensor_profile=profile, because the template accesses
        # {{ sensor_profile.device_name }}. Without it, Jinja2 raises an
        # UndefinedError and the user sees a 500 Internal Server Error.
        new_username = request.form.get("username", "").strip().lower()
        new_email = request.form.get("email", "").strip().lower()
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("password", "")

        # --- Username update ---
        if new_username and new_username != current_user.username:
            ok, err = validate_username(new_username)
            if not ok:
                flash(err, "error")
                return render_template("account.html", sensor_profile=profile)
            if User.query.filter_by(username=new_username).first():
                flash("That username is already taken.", "error")
                return render_template("account.html", sensor_profile=profile)
            current_user.username = new_username

        # --- Email update ---
        if new_email and new_email != current_user.email:
            if not validate_email(new_email):
                flash("Please enter a valid email address.", "error")
                return render_template("account.html", sensor_profile=profile)
            if User.query.filter_by(email=new_email).first():
                flash("That email is already registered.", "error")
                return render_template("account.html", sensor_profile=profile)
            current_user.email = new_email

        # --- Password update ---
        if new_password:
            if not old_password or not check_password_hash(
                current_user.password_hash, old_password
            ):
                flash("Current password is incorrect.", "error")
                return render_template("account.html", sensor_profile=profile)
            ok, err = validate_password(new_password)
            if not ok:
                flash(err, "error")
                return render_template("account.html", sensor_profile=profile)
            current_user.password_hash = generate_password_hash(
                new_password, method="scrypt"
            )

        db.session.commit()
        flash("Account updated successfully.", "success")
        return redirect(url_for("auth.account"))

    return render_template("account.html", sensor_profile=profile)
