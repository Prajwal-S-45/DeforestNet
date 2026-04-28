"""
JWT Authentication utilities for DeforestNet API.
Provides token generation, validation, and route protection.
"""

import os
from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import jwt
from flask import request, jsonify, current_app

from src.utils.logger import get_logger

logger = get_logger("auth")


class JWTManager:
    """Manages JWT token creation and validation."""

    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize JWT manager.

        Args:
            secret_key: Secret key for signing tokens (defaults to env var JWT_SECRET_KEY)
            algorithm: JWT algorithm to use
        """
        self.secret_key = secret_key or os.environ.get(
            "JWT_SECRET_KEY",
            "deforestnet-default-secret-key-change-in-production"
        )
        self.algorithm = algorithm
        self.token_expiry_hours = int(os.environ.get("JWT_TOKEN_EXPIRY_HOURS", "24"))

        if self.secret_key == "deforestnet-default-secret-key-change-in-production":
            logger.warning(
                "⚠️  Using default JWT secret key. Set JWT_SECRET_KEY environment variable "
                "for production use!"
            )

    def create_token(
        self,
        user_id: str,
        email: str = "",
        role: str = "user",
        additional_claims: Optional[Dict] = None
    ) -> str:
        """
        Create a JWT token.

        Args:
            user_id: Unique user identifier
            email: User email (optional)
            role: User role (e.g., 'user', 'admin', 'officer')
            additional_claims: Extra claims to include in token

        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expiry = now + timedelta(hours=self.token_expiry_hours)

        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "iat": now,
            "exp": expiry,
            "nbf": now
        }

        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Token created for user: {user_id}")
        return token

    def verify_token(self, token: str) -> Tuple[bool, Dict]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string to verify

        Returns:
            Tuple of (is_valid, payload_or_error)
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return True, payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return False, {"error": "Token has expired"}
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return False, {"error": "Invalid token"}
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False, {"error": "Token verification failed"}


def get_jwt_manager(app=None) -> JWTManager:
    """Get or create JWT manager instance."""
    if app is None:
        app = current_app
    
    if "jwt_manager" not in app.config:
        app.config["jwt_manager"] = JWTManager()
    
    return app.config["jwt_manager"]


def token_required(f):
    """
    Decorator to protect routes requiring valid JWT token.
    Expects token in Authorization header: "Bearer <token>"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"error": "Invalid authorization header format"}), 401

        if not token:
            return jsonify({"error": "Missing authorization token"}), 401

        jwt_manager = get_jwt_manager()
        is_valid, payload = jwt_manager.verify_token(token)

        if not is_valid:
            return jsonify(payload), 401

        # Pass payload to route handler via request context
        request.jwt_payload = payload
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator to protect admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check for valid token
        if not hasattr(request, "jwt_payload"):
            return jsonify({"error": "Missing authorization token"}), 401

        payload = request.jwt_payload
        if payload.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        return f(*args, **kwargs)

    return decorated_function


def optional_token(f):
    """
    Decorator for routes that work with or without a token.
    Adds jwt_payload to request if valid token provided, otherwise leaves it empty.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        request.jwt_payload = None
        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                token = auth_header.split(" ")[1]
                jwt_manager = get_jwt_manager()
                is_valid, payload = jwt_manager.verify_token(token)
                
                if is_valid:
                    request.jwt_payload = payload
            except (IndexError, Exception):
                pass  # Continue without token if invalid

        return f(*args, **kwargs)

    return decorated_function
