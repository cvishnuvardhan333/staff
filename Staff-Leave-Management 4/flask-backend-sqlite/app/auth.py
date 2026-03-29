from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request


def create_token(user_id: int, role: str) -> str:
    payload = {
        "id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _decode_token(token: str) -> dict:
    return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else None

        if not token:
            return jsonify({"message": "Missing auth token"}), 401

        try:
            payload = _decode_token(token)
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid or expired token"}), 401

        g.user = payload
        return fn(*args, **kwargs)

    return wrapper


def require_role(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "user", None)
            if not user or user.get("role") not in roles:
                return jsonify({"message": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
