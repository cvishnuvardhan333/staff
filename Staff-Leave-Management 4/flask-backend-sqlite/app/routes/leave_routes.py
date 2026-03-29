from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, make_response, request
from sqlalchemy.orm import joinedload

from ..auth import auth_required, require_role
from ..extensions import db
from ..models import Admin, Leave, Notification, Staff, Timetable
from ..services.mailer import send_mail
from ..utils.datetime_helpers import parse_datetime, to_date_string


leave_bp = Blueprint("leaves", __name__, url_prefix="/api/leaves")

ALLOWED_LEAVE_TYPES = {"casual", "medical", "emergency"}
ALLOWED_STATUSES = {"pending", "approved", "rejected"}


def _js_day_of_week(value: datetime) -> int:
    # JavaScript's Date.getDay(): 0=Sunday ... 6=Saturday
    return (value.weekday() + 1) % 7


def _date_range(start_date: datetime, end_date: datetime) -> list[datetime]:
    days: list[datetime] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current = current + timedelta(days=1)
    return days


def _diff_days(start_date: datetime, end_date: datetime) -> int:
    return max(1, (end_date.date() - start_date.date()).days + 1)


def _staff_profile(staff: Staff | None) -> dict | None:
    if not staff:
        return None
    return {
        "id": staff.id,
        "_id": staff.id,
        "name": staff.name,
        "email": staff.email,
        "department": staff.department,
        "designation": staff.designation,
    }


def _serialize_leave(leave: Leave, include_staff: bool = False) -> dict:
    data = leave.to_dict()
    if include_staff:
        data["staff"] = _staff_profile(leave.staff)
    return data


def _find_replacement_suggestions(leave: Leave) -> list[dict]:
    staff_member = Staff.query.get(leave.staffId)
    if not staff_member:
        return []

    candidates = (
        Staff.query.filter(
            Staff.department == staff_member.department,
            Staff.id != staff_member.id,
            Staff.isActive.is_(True),
        )
        .order_by(Staff.id.asc())
        .all()
    )

    if not candidates:
        return []

    candidate_ids = [candidate.id for candidate in candidates]
    overlapping_leaves = (
        Leave.query.filter(
            Leave.staffId.in_(candidate_ids),
            Leave.status == "approved",
            Leave.startDate <= leave.endDate,
            Leave.endDate >= leave.startDate,
        )
        .all()
    )

    unavailable = {item.staffId for item in overlapping_leaves}

    timetable_entries = Timetable.query.filter(Timetable.staffId.in_(candidate_ids)).all()
    timetable_map: dict[str, list[Timetable]] = {}
    for entry in timetable_entries:
        key = str(entry.staffId)
        timetable_map.setdefault(key, []).append(entry)

    days = _date_range(leave.startDate, leave.endDate)
    scored: list[tuple[Staff, int]] = []

    for candidate in candidates:
        if candidate.id in unavailable:
            continue

        entries = timetable_map.get(str(candidate.id), [])
        score = 0

        for day in days:
            target_day = _js_day_of_week(day)
            day_entry = next((entry for entry in entries if entry.dayOfWeek == target_day), None)

            if not day_entry:
                score += 1
                continue

            slots = day_entry.slots if isinstance(day_entry.slots, list) else []
            has_free_slot = any(isinstance(slot, dict) and slot.get("isFree") for slot in slots)
            if has_free_slot:
                score += 1

        scored.append((candidate, score))

    scored.sort(key=lambda item: item[1], reverse=True)

    return [
        {
            "staff": candidate.id,
            "score": score,
            "reason": "Matches free slots" if score > 0 else "No timetable conflicts",
        }
        for candidate, score in scored[:3]
    ]


def _enrich_suggestions(suggestions: list[dict] | None) -> list[dict]:
    suggestions = suggestions or []
    staff_ids = [item.get("staff") for item in suggestions if item.get("staff") is not None]
    if not staff_ids:
        return []

    profiles = Staff.query.filter(Staff.id.in_(staff_ids)).all()
    profile_map = {profile.id: _staff_profile(profile) for profile in profiles}

    enriched = []
    for item in suggestions:
        staff_id = item.get("staff")
        normalized_staff_id = None
        if staff_id is not None:
            try:
                normalized_staff_id = int(staff_id)
            except (TypeError, ValueError):
                normalized_staff_id = None
        enriched.append(
            {
                **item,
                "staffProfile": profile_map.get(normalized_staff_id) if normalized_staff_id is not None else None,
            }
        )
    return enriched


@leave_bp.post("")
@auth_required
@require_role("staff")
def apply_leave():
    payload = request.get_json(silent=True) or {}

    leave_type = payload.get("type")
    start_raw = payload.get("startDate")
    end_raw = payload.get("endDate")
    reason = payload.get("reason")

    if not leave_type or not start_raw or not end_raw or not reason:
        return jsonify({"message": "Missing required fields"}), 400

    if leave_type not in ALLOWED_LEAVE_TYPES:
        return jsonify({"message": "Invalid leave type"}), 400

    try:
        start = parse_datetime(start_raw)
        end = parse_datetime(end_raw)
    except Exception:  # noqa: BLE001
        start = None
        end = None

    if not start or not end:
        return jsonify({"message": "Invalid start or end date"}), 400

    if end < start:
        return jsonify({"message": "End date must be on or after start date"}), 400


    # --- Auto-approval rules ---
    def should_auto_approve(leave_type, days):
        if leave_type not in ALLOWED_LEAVE_TYPES:
            return False
        if leave_type == "emergency":
            return True
        if leave_type == "medical" and days <= 2:
            return True
        if days <= 1:
            return True
        if days > 3:
            return False
        return False

    days = _diff_days(start, end)
    auto_approved = should_auto_approve(leave_type, days)
    status = "approved" if auto_approved else "pending"
    print(f"DEBUG: type={leave_type}, days={days}, auto_approved={auto_approved}, status={status}")

    leave = Leave(
        staffId=g.user["id"],
        type=leave_type,
        startDate=start,
        endDate=end,
        reason=str(reason),
        status=status,
        autoApproved=auto_approved,
    )
    db.session.add(leave)

    admins = Admin.query.all()
    for admin in admins:
        db.session.add(
            Notification(
                recipientRole="admin",
                recipientId=admin.id,
                message="New leave request submitted",
                type="leave",
            )
        )

    # Notify staff if auto-approved
    if auto_approved:
        db.session.add(
            Notification(
                recipientRole="staff",
                recipientId=g.user["id"],
                message="Your leave request was auto-approved.",
                type="leave",
            )
        )

    db.session.commit()
    return jsonify(_serialize_leave(leave)), 201


@leave_bp.get("/me")
@auth_required
@require_role("staff")
def get_my_leaves():
    leaves = Leave.query.filter_by(staffId=g.user["id"]).order_by(Leave.createdAt.desc()).all()
    return jsonify([_serialize_leave(leave) for leave in leaves])


@leave_bp.get("")
@auth_required
@require_role("admin")
def get_all_leaves():
    leaves = Leave.query.options(joinedload(Leave.staff)).order_by(Leave.createdAt.desc()).all()
    return jsonify([_serialize_leave(leave, include_staff=True) for leave in leaves])


@leave_bp.patch("/<int:leave_id>/status")
@auth_required
@require_role("admin")
def update_leave_status(leave_id: int):
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")

    if status not in ALLOWED_STATUSES:
        return jsonify({"message": "Invalid status value"}), 400

    leave = Leave.query.get(leave_id)
    if not leave:
        return jsonify({"message": "Leave not found"}), 404

    if leave.status == status:
        return jsonify(_serialize_leave(leave))

    previous_status = leave.status
    leave.status = status
    leave.approvedById = g.user["id"] if status != "pending" else None

    if previous_status != status:
        days = _diff_days(leave.startDate, leave.endDate)

        if previous_status != "approved" and status == "approved":
            staff = Staff.query.get(leave.staffId)
            if staff:
                staff.leaveBalanceUsed = (staff.leaveBalanceUsed or 0) + days

        if previous_status == "approved" and status != "approved":
            staff = Staff.query.get(leave.staffId)
            if staff:
                staff.leaveBalanceUsed = max(0, (staff.leaveBalanceUsed or 0) - days)

    leave.replacementSuggestions = _find_replacement_suggestions(leave)

    db.session.add(
        Notification(
            recipientRole="staff",
            recipientId=leave.staffId,
            message=f"Your leave request was {status}.",
            type="leave",
        )
    )

    db.session.commit()

    if status in {"approved", "rejected"}:
        try:
            staff = Staff.query.get(leave.staffId)
            if staff and staff.email:
                subject = "Leave approved" if status == "approved" else "Leave rejected"
                reason_line = f"Reason: {leave.reason}\n" if leave.reason else ""
                send_mail(
                    to=staff.email,
                    subject=subject,
                    text=(
                        f"Hello {staff.name or 'Faculty'},\n\n"
                        f"Your leave request has been {status}.\n\n"
                        f"Dates: {to_date_string(leave.startDate)} to {to_date_string(leave.endDate)}\n"
                        f"Type: {leave.type}\n"
                        f"{reason_line}\n"
                        "Thank you."
                    ),
                )
        except Exception:
            pass

    return jsonify(_serialize_leave(leave))


@leave_bp.get("/active")
@auth_required
@require_role("admin")
def get_active_leaves():
    now = datetime.utcnow()
    start_of_today = datetime(now.year, now.month, now.day)
    end_of_today = start_of_today + timedelta(days=1) - timedelta(milliseconds=1)

    leaves = (
        Leave.query.options(joinedload(Leave.staff))
        .filter(
            Leave.status == "approved",
            Leave.startDate <= end_of_today,
            Leave.endDate >= start_of_today,
        )
        .order_by(Leave.startDate.asc())
        .all()
    )

    enriched = []
    for leave in leaves:
        raw_suggestions = leave.replacementSuggestions if isinstance(leave.replacementSuggestions, list) else None
        if raw_suggestions is None:
            raw_suggestions = _find_replacement_suggestions(leave)

        payload = _serialize_leave(leave, include_staff=True)
        payload["replacementSuggestions"] = _enrich_suggestions(raw_suggestions)
        enriched.append(payload)

    return jsonify(enriched)


@leave_bp.patch("/<int:leave_id>/replacement")
@auth_required
@require_role("admin")
def assign_replacement(leave_id: int):
    payload = request.get_json(silent=True) or {}
    staff_id_raw = payload.get("staffId")

    if staff_id_raw is None:
        return jsonify({"message": "Replacement staff is required"}), 400

    try:
        staff_id = int(staff_id_raw)
    except (TypeError, ValueError):
        return jsonify({"message": "Replacement staff is required"}), 400

    leave = Leave.query.get(leave_id)
    if not leave:
        return jsonify({"message": "Leave not found"}), 404

    if leave.status != "approved":
        return jsonify({"message": "Replacement can only be assigned to approved leave"}), 400

    current = leave.replacementSuggestions if isinstance(leave.replacementSuggestions, list) else _find_replacement_suggestions(leave)

    normalized = []
    for item in current:
        current_staff = item.get("staff")
        try:
            current_staff = int(current_staff)
        except (TypeError, ValueError):
            pass

        normalized.append(
            {
                **item,
                "staff": current_staff,
                "assigned": current_staff == staff_id,
            }
        )

    exists = any(item.get("staff") == staff_id for item in normalized)
    if not exists:
        normalized.append({"staff": staff_id, "score": 0, "reason": "Manually assigned", "assigned": True})

    leave.replacementSuggestions = normalized
    db.session.commit()

    replacement = Staff.query.get(staff_id)
    leave_owner = Staff.query.get(leave.staffId)

    if replacement:
        db.session.add(
            Notification(
                recipientRole="staff",
                recipientId=replacement.id,
                message=(
                    f"You have been assigned to replace {leave_owner.name if leave_owner else 'a faculty'} "
                    f"during leave dates {to_date_string(leave.startDate)} to {to_date_string(leave.endDate)}."
                ),
                type="leave",
            )
        )
        db.session.commit()

        if replacement.email:
            try:
                send_mail(
                    to=replacement.email,
                    subject="Replacement assignment",
                    text=(
                        f"Hello {replacement.name or 'Faculty'},\n\n"
                        f"You have been assigned to replace {leave_owner.name if leave_owner else 'a faculty'} "
                        "during the approved leave period.\n\n"
                        f"Dates: {to_date_string(leave.startDate)} to {to_date_string(leave.endDate)}\n"
                        f"Department: {leave_owner.department if leave_owner else 'N/A'}\n"
                        f"Designation: {leave_owner.designation if leave_owner else 'N/A'}\n\n"
                        "Thank you."
                    ),
                )
            except Exception:
                pass

    suggestions = _enrich_suggestions(normalized)
    return jsonify({"_id": leave.id, "replacementSuggestions": suggestions})


@leave_bp.get("/stats")
@auth_required
def get_leave_stats():
    is_staff = g.user.get("role") == "staff"
    filter_args = {"staffId": g.user["id"]} if is_staff else {}

    total = Leave.query.filter_by(**filter_args).count()
    approved = Leave.query.filter_by(**filter_args, status="approved").count()
    rejected = Leave.query.filter_by(**filter_args, status="rejected").count()
    pending = Leave.query.filter_by(**filter_args, status="pending").count()

    return jsonify({"total": total, "approved": approved, "rejected": rejected, "pending": pending})


@leave_bp.get("/analytics")
@auth_required
@require_role("admin")
def get_leave_analytics():
    rows = Leave.query.all()

    month_map: dict[int, dict] = {}
    for leave in rows:
        if not leave.startDate:
            continue
        month = int(leave.startDate.month)
        if month not in month_map:
            month_map[month] = {"_id": month, "total": 0, "approved": 0, "rejected": 0}

        month_map[month]["total"] += 1
        if leave.status == "approved":
            month_map[month]["approved"] += 1
        if leave.status == "rejected":
            month_map[month]["rejected"] += 1

    normalized = [month_map[key] for key in sorted(month_map.keys())]
    return jsonify(normalized)


@leave_bp.get("/<int:leave_id>/suggestions")
@auth_required
@require_role("admin")
def get_leave_suggestions(leave_id: int):
    leave = Leave.query.get(leave_id)
    if not leave:
        return jsonify({"message": "Leave not found"}), 404

    suggestions = _find_replacement_suggestions(leave)
    enriched = _enrich_suggestions(suggestions)
    leave.replacementSuggestions = suggestions
    db.session.commit()

    return jsonify(enriched)


@leave_bp.get("/export")
@auth_required
@require_role("admin")
def export_leaves():
    leaves = Leave.query.options(joinedload(Leave.staff)).all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["Staff Name", "Email", "Department", "Designation", "Type", "Start Date", "End Date", "Status", "Reason"])

    for leave in leaves:
        writer.writerow(
            [
                leave.staff.name if leave.staff else "",
                leave.staff.email if leave.staff else "",
                leave.staff.department if leave.staff else "",
                leave.staff.designation if leave.staff else "",
                leave.type,
                to_date_string(leave.startDate),
                to_date_string(leave.endDate),
                leave.status,
                leave.reason or "",
            ]
        )

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = 'attachment; filename="leave-report.csv"'
    return response
