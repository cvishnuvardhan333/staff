from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request
from ..auth import auth_required, create_token
from ..extensions import db
from ..models import Admin, Staff
from ..services.mailer import send_mail
from ..utils.security import check_password_hash_compat, generate_password_hash_compat


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _normalize_email(value: str) -> str:
    return value.strip().lower()


@auth_bp.post("/staff/login")
def login_staff():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    staff = Staff.query.filter_by(email=email).first()
    if not staff:
        return jsonify({"message": "Invalid credentials"}), 401

    if staff.isActive is False:
        return jsonify({"message": "Account is inactive"}), 403

    if not check_password_hash_compat(staff.password, password):
        return jsonify({"message": "Invalid credentials"}), 401

    token = create_token(staff.id, staff.role)
    return jsonify(
        {
            "token": token,
            "user": {
                "id": staff.id,
                "name": staff.name,
                "role": staff.role,
                "department": staff.department,
                "email": staff.email,
            },
        }
    )


@auth_bp.post("/admin/login")
def login_admin():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    admin = Admin.query.filter_by(email=email).first()
    if not admin:
        return jsonify({"message": "Invalid credentials"}), 401

    if not check_password_hash_compat(admin.password, password):
        return jsonify({"message": "Invalid credentials"}), 401

    token = create_token(admin.id, admin.role)
    return jsonify(
        {
            "token": token,
            "user": {
                "id": admin.id,
                "name": admin.name,
                "role": admin.role,
                "email": admin.email,
            },
        }
    )


@auth_bp.get("/me")
@auth_required
def me():
    role = g.user.get("role")
    user_id = g.user.get("id")

    if role == "admin":
        admin = Admin.query.get(user_id)
        return jsonify(admin.to_dict() if admin else None)

    staff = Staff.query.get(user_id)
    return jsonify(staff.to_dict() if staff else None)


@auth_bp.post("/staff/register")
def register_staff():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email_raw = payload.get("email") or ""
    password = payload.get("password") or ""
    department = (payload.get("department") or "").strip()
    designation = (payload.get("designation") or "").strip() or None
    phone = (payload.get("phone") or "").strip() or None

    if not name or not email_raw or not password or not department:
        return jsonify({"message": "Missing required fields"}), 400

    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400

    email = _normalize_email(email_raw)
    existing = Staff.query.filter_by(email=email).first()
    if existing:
        return jsonify({"message": "Staff account already exists"}), 409

    staff = Staff(
        name=name,
        email=email,
        password=generate_password_hash_compat(password),
        department=department,
        designation=designation or "Faculty",
        phone=phone,
    )
    db.session.add(staff)
    db.session.commit()

    token = create_token(staff.id, staff.role)
    return (
        jsonify(
            {
                "token": token,
                "user": {
                    "id": staff.id,
                    "name": staff.name,
                    "role": staff.role,
                    "department": staff.department,
                    "email": staff.email,
                },
            }
        ),
        201,
    )


@auth_bp.put("/profile")
@auth_required
def update_profile():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email_raw = payload.get("email") or ""

    if not name or not email_raw:
        return jsonify({"message": "Name and email are required"}), 400

    email = _normalize_email(email_raw)

    if g.user.get("role") == "admin":
        admin = Admin.query.get(g.user.get("id"))
        if not admin:
            return jsonify({"message": "Admin not found"}), 404

        if email != admin.email:
            exists = Admin.query.filter(Admin.email == email, Admin.id != admin.id).first()
            if exists:
                return jsonify({"message": "Email already in use"}), 409

        admin.name = name
        admin.email = email
        db.session.commit()

        return jsonify({"id": admin.id, "name": admin.name, "role": admin.role, "email": admin.email})

    staff = Staff.query.get(g.user.get("id"))
    if not staff:
        return jsonify({"message": "Staff member not found"}), 404

    if email != staff.email:
        exists = Staff.query.filter(Staff.email == email, Staff.id != staff.id).first()
        if exists:
            return jsonify({"message": "Email already in use"}), 409

    department = payload.get("department")
    designation = payload.get("designation")
    phone = payload.get("phone")
    avatar_url = payload.get("avatarUrl")

    staff.name = name
    staff.email = email
    if isinstance(department, str) and department.strip():
        staff.department = department.strip()
    if isinstance(designation, str) and designation.strip():
        staff.designation = designation.strip()
    if isinstance(phone, str):
        staff.phone = phone.strip() or staff.phone
    if isinstance(avatar_url, str):
        staff.avatarUrl = avatar_url.strip() or staff.avatarUrl

    db.session.commit()

    return jsonify(
        {
            "id": staff.id,
            "name": staff.name,
            "role": staff.role,
            "department": staff.department,
            "email": staff.email,
            "designation": staff.designation,
            "phone": staff.phone,
            "avatarUrl": staff.avatarUrl,
        }
    )


@auth_bp.post("/forgot-password")
def forgot_password():
    payload = request.get_json(silent=True) or {}
    email_raw = payload.get("email")

    if not isinstance(email_raw, str) or not email_raw.strip():
        return jsonify({"message": "Email is required"}), 400

    email = _normalize_email(email_raw)

    staff = Staff.query.filter_by(email=email).first()
    admin = None if staff else Admin.query.filter_by(email=email).first()
    user = staff or admin

    if not user:
        return jsonify({"message": "If the email exists, a reset link has been sent."})

    reset_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()

    user.resetToken = token_hash
    user.resetTokenExpires = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    app_url = current_app.config.get("APP_URL") or current_app.config.get("FRONTEND_URL") or "http://localhost:5173"
    reset_link = f"{app_url}/reset-password?token={reset_token}&email={email}"

    try:
        send_mail(
            to=email,
            subject="Reset your Smart Staff password",
            text=(
                "Use the link below to reset your password. This link expires in 1 hour.\n\n"
                f"{reset_link}"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": str(exc) or "Unable to send reset email"}), 400

    return jsonify({"message": "If the email exists, a reset link has been sent."})


@auth_bp.post("/reset-password")
def reset_password():
    payload = request.get_json(silent=True) or {}
    email_raw = payload.get("email")
    token = payload.get("token")
    password = payload.get("password")

    if not email_raw or not token or not password:
        return jsonify({"message": "Email, token, and password are required"}), 400

    email = _normalize_email(str(email_raw))
    token_hash = hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    now = datetime.utcnow()

    staff = Staff.query.filter_by(email=email, resetToken=token_hash).first()
    admin = None if staff else Admin.query.filter_by(email=email, resetToken=token_hash).first()
    user = staff or admin

    if not user or not user.resetTokenExpires or user.resetTokenExpires < now:
        return jsonify({"message": "Reset link is invalid or expired"}), 400

    user.password = generate_password_hash(str(password))
    user.resetToken = None
    user.resetTokenExpires = None
    db.session.commit()

    return jsonify({"message": "Password updated successfully"})
