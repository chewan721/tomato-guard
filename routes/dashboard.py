from flask import Blueprint, render_template
from flask_login import login_required, current_user
from extensions import db
import logging

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard_bp', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        from model import SensorData, SensorProfile
        
        # Find all unique chip_ids from SensorData
        unpaired_chips = db.session.query(SensorData.chip_id)\
            .filter(SensorData.chip_id.isnot(None))\
            .distinct()\
            .all()
        
        unpaired_chips = [c[0] for c in unpaired_chips]
        
        # Get already paired chips for this user
        paired_chips = [p.chip_id for p in SensorProfile.query.filter_by(user_id=current_user.id).all() if p.chip_id]
        
        # Filter to only unpaired
        unpaired = [chip for chip in unpaired_chips if chip not in paired_chips]
        
        # Get latest reading for each unpaired chip
        unpaired_devices = []
        for chip in unpaired:
            latest = SensorData.query.filter_by(chip_id=chip)\
                .order_by(SensorData.timestamp.desc())\
                .first()
            
            if latest:
                unpaired_devices.append({
                    "chip_id": chip,
                    "last_seen": latest.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    "last_temperature": latest.temperature,
                    "last_humidity": latest.humidity,
                    "last_soil": latest.soil_moisture
                })      
        return render_template('dashboard.html', unpaired_devices=unpaired_devices)
   
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        # Return dashboard even if unpaired devices query fails
        return render_template('dashboard.html', unpaired_devices=[])
    