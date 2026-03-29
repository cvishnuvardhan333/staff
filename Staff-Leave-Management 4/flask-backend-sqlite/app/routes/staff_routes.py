from __future__ import annotations

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..auth import auth_required, require_role
from ..extensions import db
from ..models import Leave, Notification, Staff, Timetable


staff_bp = Blueprint("staff", __name__, url_prefix="/api/staff")


@staff_bp.get("")
@auth_required
@require_role("admin")
def get_all_staff():
    members = Staff.query.order_by(Staff.createdAt.desc()).all()
    return jsonify([member.to_dict() for member in members])


@staff_bp.post("")
@auth_required
@require_role("admin")
def create_staff():
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

    email = email_raw.strip().lower()
    existing = Staff.query.filter_by(email=email).first()
    if existing:
        return jsonify({"message": "Staff account already exists"}), 409

    staff = Staff(
        name=name,
        email=email,
        password=generate_password_hash(password),
        department=department,
        designation=designation or "Faculty",
        phone=phone,
    )

    db.session.add(staff)
    db.session.commit()

    return jsonify({"id": staff.id}), 201


@staff_bp.delete("/<int:staff_id>")
@auth_required
@require_role("admin")
def delete_staff(staff_id: int):
    staff = Staff.query.get(staff_id)
    if not staff:
        return jsonify({"message": "Staff member not found"}), 404

    try:
        Leave.query.filter_by(staffId=staff_id).delete(synchronize_session=False)
        Timetable.query.filter_by(staffId=staff_id).delete(synchronize_session=False)
        Notification.query.filter_by(recipientRole="staff", recipientId=staff_id).delete(synchronize_session=False)

        db.session.delete(staff)
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        message = str(exc).strip() or "Unable to delete staff member"
        return jsonify({"message": message}), 400

    return jsonify({"id": staff.id, "deleted": True})
