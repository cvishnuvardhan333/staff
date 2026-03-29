from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..auth import auth_required, require_role
from ..extensions import db
from ..models import Timetable


timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/timetable")


@timetable_bp.get("/staff/<int:staff_id>")
@auth_required
def get_staff_timetable(staff_id: int):
    entries = Timetable.query.filter_by(staffId=staff_id).order_by(Timetable.dayOfWeek.asc()).all()
    return jsonify([entry.to_dict() for entry in entries])


@timetable_bp.post("/staff/<int:staff_id>")
@auth_required
@require_role("admin")
def upsert_staff_timetable(staff_id: int):
    payload = request.get_json(silent=True) or {}
    day_of_week = payload.get("dayOfWeek")
    slots = payload.get("slots")
    department = payload.get("department")

    existing = Timetable.query.filter_by(staffId=staff_id, dayOfWeek=day_of_week).first()
    if existing:
        existing.staffId = staff_id
        existing.dayOfWeek = day_of_week
        existing.slots = slots
        existing.department = department
        db.session.commit()
        return jsonify(existing.to_dict())

    entry = Timetable(
        staffId=staff_id,
        dayOfWeek=day_of_week,
        slots=slots,
        department=department,
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict())
