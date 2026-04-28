"""
DeforestNet - Prediction API Routes
Upload images and get deforestation predictions.
"""

import os
import uuid
import numpy as np
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app, send_file
from src.utils.logger import get_logger
from src.api.auth import token_required
from configs.config import PREDICTIONS_DIR, VISUALIZATION_DIR

logger = get_logger("api.predictions")

predictions_bp = Blueprint("predictions", __name__)

# Store recent predictions in memory for quick access
_recent_predictions = {}


def _send_auto_notification(alert):
    """Send notification automatically after alert creation."""
    notif_manager = current_app.config.get("NOTIFICATION_MANAGER")
    if notif_manager is None:
        return {
            "attempted": False,
            "success": False,
            "error": "Notification manager not configured",
            "successful_tiers": [],
            "failed_tiers": []
        }

    try:
        result = notif_manager.send_alert_notification(alert, tiers=["email"])
        return {
            "attempted": True,
            "success": result.success,
            "successful_tiers": result.successful_tiers,
            "failed_tiers": result.failed_tiers,
            "details": result.tier_results
        }
    except Exception as e:
        logger.error(f"Auto-notification failed for alert {alert.alert_id}: {e}")
        return {
            "attempted": True,
            "success": False,
            "error": str(e),
            "successful_tiers": [],
            "failed_tiers": ["email"]
        }


@predictions_bp.route("/analyze", methods=["POST"])
@token_required
def analyze_prediction():
    """
    Analyze a prediction mask for deforestation.
    
    **Requires JWT authentication** (Bearer token in Authorization header)

    Accepts JSON with prediction and confidence arrays,
    or generates a demo prediction.

    Request JSON:
        prediction: 2D array of class labels (optional)
        confidence: 2D array of confidence scores (optional)
        latitude: float (optional)
        longitude: float (optional)
        region: str (optional)
        demo: bool - generate demo data (default: true)
    """
    manager = current_app.config["ALERT_MANAGER"]
    data = request.get_json(silent=True) or {}

    latitude = data.get("latitude", 0.0)
    longitude = data.get("longitude", 0.0)
    region = data.get("region", "")
    use_demo = data.get("demo", True)

    if use_demo or "prediction" not in data:
        # Generate demo prediction
        prediction, confidence = _generate_demo_prediction()
    else:
        try:
            prediction = np.array(data["prediction"], dtype=np.int64)
            confidence = np.array(data.get("confidence",
                                           np.ones_like(prediction) * 0.85),
                                  dtype=np.float32)
        except Exception as e:
            return jsonify({"error": f"Invalid prediction data: {e}"}), 400

    # Process through alert manager
    alert = manager.process_prediction(
        prediction, confidence,
        latitude=latitude,
        longitude=longitude,
        region=region
    )

    if alert is None:
        return jsonify({
            "deforestation_detected": False,
            "message": "No significant deforestation detected",
            "prediction_shape": list(prediction.shape)
        })

    # Store prediction for later retrieval
    pred_id = alert.alert_id
    _recent_predictions[pred_id] = {
        "prediction": prediction.tolist(),
        "alert": alert.to_dict()
    }

    notification_result = _send_auto_notification(alert)

    return jsonify({
        "deforestation_detected": True,
        "alert": alert.to_dict(),
        "prediction_id": pred_id,
        "prediction_shape": list(prediction.shape),
        "notification": notification_result
    })


@predictions_bp.route("/demo", methods=["POST"])
@token_required
def demo_prediction():
    """
    Generate a demo prediction and alert.
    
    **Requires JWT authentication** (Bearer token in Authorization header)

    Request JSON (all optional):
        cause: str - deforestation cause (Logging, Mining, Agriculture, Fire, Infrastructure)
        latitude: float
        longitude: float
        region: str
        area_fraction: float - fraction of image with deforestation (0.0-1.0)
    """
    from configs.config import CLASS_NAMES

    manager = current_app.config["ALERT_MANAGER"]
    data = request.get_json(silent=True) or {}

    cause = data.get("cause", "Mining")
    latitude = data.get("latitude", 10.5)
    longitude = data.get("longitude", 76.3)
    region = data.get("region", "Western Ghats")
    area_fraction = min(max(data.get("area_fraction", 0.25), 0.05), 0.9)

    # Map cause to class index
    cause_to_class = {name: i for i, name in enumerate(CLASS_NAMES)}
    class_idx = cause_to_class.get(cause, 2)

    # Generate prediction
    size = 256
    prediction = np.zeros((size, size), dtype=np.int64)
    confidence = np.full((size, size), 0.9, dtype=np.float32)

    # Create deforestation region
    side = int(size * (area_fraction ** 0.5))
    start = (size - side) // 2
    prediction[start:start+side, start:start+side] = class_idx

    # Add some noise to confidence
    confidence += np.random.uniform(-0.05, 0.05, (size, size)).astype(np.float32)
    confidence = np.clip(confidence, 0.7, 0.99)

    # Process
    alert = manager.process_prediction(
        prediction, confidence,
        latitude=latitude,
        longitude=longitude,
        region=region
    )

    if alert is None:
        return jsonify({
            "deforestation_detected": False,
            "message": "Area too small or confidence too low"
        })

    notification_result = _send_auto_notification(alert)

    return jsonify({
        "deforestation_detected": True,
        "alert": alert.to_dict(),
        "demo": True,
        "notification": notification_result
    })


@predictions_bp.route("/recent", methods=["GET"])
def get_recent_predictions():
    """Get recent prediction results."""
    limit = request.args.get("limit", 10, type=int)

    recent = list(_recent_predictions.values())[-limit:]
    return jsonify({
        "predictions": [p["alert"] for p in recent],
        "count": len(recent)
    })


def _generate_demo_prediction():
    """Generate a demo prediction with random deforestation."""
    import random

    size = 256
    prediction = np.zeros((size, size), dtype=np.int64)
    confidence = np.full((size, size), 0.85, dtype=np.float32)

    # Random deforestation cause (1-5)
    cause_class = random.randint(1, 5)

    # Random deforestation area (15-40% of image)
    area_fraction = random.uniform(0.15, 0.40)
    side = int(size * (area_fraction ** 0.5))
    x_start = random.randint(0, size - side)
    y_start = random.randint(0, size - side)

    prediction[y_start:y_start+side, x_start:x_start+side] = cause_class

    # Randomize confidence
    confidence += np.random.uniform(-0.1, 0.1, (size, size)).astype(np.float32)
    confidence = np.clip(confidence, 0.6, 0.99)

    return prediction, confidence
