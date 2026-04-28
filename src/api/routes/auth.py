"""
Authentication routes for DeforestNet API.
Provides login endpoint to obtain JWT tokens.
"""

from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from src.utils.logger import get_logger
from src.api.auth import get_jwt_manager

logger = get_logger("auth_routes")

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login endpoint to obtain JWT token.
    
    Expected JSON:
    {
        "user_id": "officer123",
        "email": "officer@example.com",
        "password": "your_password",
        "role": "officer"  # Optional, defaults to "user"
    }
    
    Returns:
    {
        "success": true,
        "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "user_id": "officer123",
        "email": "officer@example.com",
        "role": "officer",
        "expires_in_hours": 24
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Validate required fields
        user_id = data.get("user_id", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
        role = data.get("role", "user").strip().lower()

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if not password:
            return jsonify({"error": "password is required"}), 400

        # ==================== AUTHENTICATION LOGIC ====================
        # TODO: Implement your authentication logic here.
        # Current implementation: Simple validation (DEMO MODE)
        # 
        # In production, you should:
        # 1. Query officer/user database for credentials
        # 2. Hash and verify password using bcrypt/argon2
        # 3. Check user permissions
        # 4. Update last_login timestamp
        #
        # Example with database:
        # user = db.get_officer_by_id(user_id)
        # if not user or not verify_password(password, user.password_hash):
        #     return jsonify({"error": "Invalid credentials"}), 401

        # Demo mode: Accept any password for demo users
        demo_users = {
            "officer1": {"role": "officer", "email": "officer1@deforestnet.org"},
            "admin": {"role": "admin", "email": "admin@deforestnet.org"},
            "demo": {"role": "user", "email": "demo@deforestnet.org"}
        }

        if user_id not in demo_users:
            logger.warning(f"Login failed: unknown user {user_id}")
            return jsonify({"error": "Invalid user_id or password"}), 401

        # In demo mode, accept the password; in production, verify hash
        user_info = demo_users[user_id]
        email = email or user_info["email"]
        role = role or user_info["role"]

        # ==================== TOKEN GENERATION ====================
        jwt_manager = get_jwt_manager(current_app)
        token = jwt_manager.create_token(
            user_id=user_id,
            email=email,
            role=role,
            additional_claims={"login_time": datetime.utcnow().isoformat()}
        )

        logger.info(f"User logged in: {user_id} ({role})")

        return jsonify({
            "success": True,
            "token": token,
            "user_id": user_id,
            "email": email,
            "role": role,
            "expires_in_hours": jwt_manager.token_expiry_hours,
            "message": "Login successful. Include token in Authorization header: 'Bearer <token>'"
        }), 200

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Login failed", "message": str(e)}), 500


@auth_bp.route("/validate", methods=["GET"])
def validate_token():
    """
    Validate current JWT token.
    Requires: Authorization header with valid token.
    
    Returns:
    {
        "valid": true,
        "user_id": "officer123",
        "email": "officer@example.com",
        "role": "officer",
        "expires_at": "2026-04-29T16:30:00"
    }
    """
    from src.api.auth import token_required
    
    # This endpoint requires a valid token (handled by decorator below)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Missing authorization token"}), 401

    try:
        token = auth_header.split(" ")[1]
        jwt_manager = get_jwt_manager(current_app)
        is_valid, payload = jwt_manager.verify_token(token)

        if not is_valid:
            return jsonify({
                "valid": False,
                "error": payload.get("error", "Invalid token")
            }), 401

        return jsonify({
            "valid": True,
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "expires_at": payload.get("exp")  # Unix timestamp
        }), 200

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return jsonify({"valid": False, "error": "Validation failed"}), 500


@auth_bp.route("/refresh", methods=["POST"])
def refresh_token():
    """
    Refresh JWT token (extend expiration).
    Requires: Valid current token in Authorization header.
    
    Returns: New JWT token with extended expiration
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Missing authorization token"}), 401

    try:
        token = auth_header.split(" ")[1]
        jwt_manager = get_jwt_manager(current_app)
        is_valid, payload = jwt_manager.verify_token(token)

        if not is_valid:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Create new token with same claims
        new_token = jwt_manager.create_token(
            user_id=payload.get("user_id"),
            email=payload.get("email"),
            role=payload.get("role")
        )

        logger.info(f"Token refreshed for user: {payload.get('user_id')}")

        return jsonify({
            "success": True,
            "token": new_token,
            "expires_in_hours": jwt_manager.token_expiry_hours,
            "message": "Token refreshed successfully"
        }), 200

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({"error": "Token refresh failed"}), 500
