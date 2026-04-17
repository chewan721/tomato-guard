import os
import logging
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from utils.ml_model import predict_disease, DISEASE_CURES, validate_leaf_image
from utils.groq_client import get_ai_cure
from model import DiseaseHistory, db

disease_bp = Blueprint("disease", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename: str) -> bool:
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def _delete_upload_file(filename: str) -> None:
    if not filename:
        return
    filepath = os.path.join(current_app.root_path, "static", "uploads", filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Deleted file: {filename}")
    except OSError as exc:
        logger.error(f"Could not delete upload file {filepath}: {exc}")

def _save_uploaded_file(file):
    """Returns (filepath, stored_filename, original_filename, error_msg)"""
    try:
        if not file or file.filename == "":
            return None, None, None, "No file selected."

        if not allowed_file(file.filename):
            return None, None, None, "Invalid file type. Please upload PNG, JPG, JPEG, or WEBP images."

        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > MAX_FILE_SIZE:
            return None, None, None, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB."

        upload_dir = os.path.join(current_app.root_path, "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        original_filename = secure_filename(file.filename)
        ext = original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else ""
        stored_filename = f"{uuid.uuid4().hex}.{ext}" if ext else f"{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(upload_dir, stored_filename)

        file.save(filepath)
        logger.info(f"Saved: {stored_filename} (original: {original_filename})")
        return filepath, stored_filename, original_filename, None

    except Exception as exc:
        logger.error(f"Failed to save uploaded file: {exc}", exc_info=True)
        return None, None, None, "Failed to save uploaded file. Please try again."

@disease_bp.route("/disease", methods=["GET", "POST"])
@login_required
def disease():
    uploaded_file = None
    disease_name = None
    cure = None
    confidence = None
    validation_error = None

    if request.method == "POST":
        if "leaf_image" not in request.files:
            flash("No file selected.", "error")
            return redirect(request.url)

        file = request.files["leaf_image"]
        filepath, stored_filename, original_filename, error_msg = _save_uploaded_file(file)

        if error_msg:
            flash(error_msg, "error")
            return redirect(request.url)

        uploaded_file = stored_filename

        try:
            # Fast basic check only (detailed validation is slow)
            is_valid, validation_msg = validate_leaf_image(filepath)

            if not is_valid:
                logger.warning(f"Invalid leaf image: {validation_msg}")
                _delete_upload_file(stored_filename)
                flash(f"Invalid image: {validation_msg}", "error")
                return render_template("disease.html", validation_error=validation_msg)

            # Proceed with disease prediction (now uses fast internal check)
            disease_name, static_cure, confidence = predict_disease(filepath)

            if disease_name == "Model not loaded":
                _delete_upload_file(stored_filename)
                flash("Disease detection service is temporarily unavailable. Please try again later.", "error")
                return redirect(request.url)

            if disease_name == "Invalid Image":
                _delete_upload_file(stored_filename)
                flash("Please upload a clear photo of a tomato leaf.", "error")
                return render_template("disease.html", validation_error="Not a valid tomato leaf image")

            if disease_name == "Unknown / Low Confidence":
                flash("The image quality is too low for accurate detection. Please upload a clearer photo of the leaf.", "warning")

            verified_link = static_cure.get("learn_more")
            logger.info(f"Disease detected: {disease_name} | Confidence: {confidence:.2%}")

            cure = dict(static_cure)

            ai_cure_enabled = current_app.config.get("AI_CURE_ENABLED", False)
            if ai_cure_enabled and confidence >= 0.60 and disease_name not in ["Invalid Image", "Unknown / Low Confidence", "Model not loaded"]:
                try:
                    logger.info(f"Fetching AI cure for {disease_name}...")
                    ai_cure = get_ai_cure(disease_name, confidence, filepath)
                    cure = dict(ai_cure)
                    cure["learn_more"] = verified_link
                except Exception as exc:
                    logger.error(f"AI cure failed, using static: {exc}")
                    cure = dict(static_cure)

            record = DiseaseHistory(
                user_id=current_user.id,
                disease_name=disease_name,
                confidence=confidence,
                image_filename=stored_filename,
                original_filename=original_filename or stored_filename,
            )
            db.session.add(record)
            db.session.commit()

            if confidence >= 0.85:
                flash(f"Detection successful! {disease_name} detected with high confidence.", "success")
            elif confidence >= 0.60:
                flash(f"Detection completed with moderate confidence. Please verify the result.", "info")

        except Exception as exc:
            db.session.rollback()
            _delete_upload_file(stored_filename)
            logger.error(f"Disease detection failed: {exc}", exc_info=True)
            flash("An unexpected error occurred. Please try again.", "error")
            return redirect(request.url)

    return render_template(
        "disease.html",
        uploaded_file=uploaded_file,
        disease_name=disease_name,
        cure=cure,
        confidence=confidence,
        validation_error=validation_error,
    )


@disease_bp.route("/disease/history")
@login_required
def disease_history():
    from datetime import datetime, timedelta
    from model import _nepal_now
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to last 7 days if no dates provided
    if not start_date and not end_date:
        today = _nepal_now().date()
        seven_days_ago = today - timedelta(days=7)
        start_date = str(seven_days_ago)
        end_date = str(today)
    
    query = DiseaseHistory.query.filter_by(user_id=current_user.id)
    
    if start_date:
        try:
            query = query.filter(DiseaseHistory.timestamp >= start_date)
        except: pass
    if end_date:
        try:
            # End date should include the whole day
            query = query.filter(DiseaseHistory.timestamp <= f"{end_date} 23:59:59")
        except: pass

    records = query.order_by(DiseaseHistory.timestamp.desc()).all()
    
    # Pass now and timedelta to template for quick filter links
    from datetime import timedelta
    return render_template("disease_history.html", 
                         records=records, 
                         start_date=start_date, 
                         end_date=end_date,
                         now=_nepal_now(),
                         timedelta=timedelta)


@disease_bp.route("/disease/history/delete/<int:record_id>", methods=["POST"])
@login_required
def delete_disease_history(record_id):
    record = DiseaseHistory.query.filter_by(id=record_id, user_id=current_user.id).first()
    if not record:
        flash("History record not found.", "error")
        return redirect(url_for("disease.disease_history"))

    try:
        _delete_upload_file(record.image_filename)
        db.session.delete(record)
        db.session.commit()
        flash("History record deleted.", "success")
    except Exception as exc:
        db.session.rollback()
        logger.error("Failed to delete disease history record: %s", exc)
        flash("Could not delete history record.", "error")

    return redirect(url_for("disease.disease_history"))


@disease_bp.route("/disease/history/delete-all", methods=["POST"])
@login_required
def delete_all_disease_history():
    records = DiseaseHistory.query.filter_by(user_id=current_user.id).all()
    if not records:
        flash("No history records found.", "error")
        return redirect(url_for("disease.disease_history"))

    try:
        for record in records:
            _delete_upload_file(record.image_filename)

        deleted_count = DiseaseHistory.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash(f"{deleted_count} history record(s) deleted.", "success")
    except Exception as exc:
        db.session.rollback()
        logger.error("Failed to delete all disease history records: %s", exc)
        flash("Could not delete history records.", "error")

    return redirect(url_for("disease.disease_history"))