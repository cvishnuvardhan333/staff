from __future__ import annotations

from flask import Blueprint, g, jsonify

from ..auth import auth_required
from ..extensions import db
from ..models import Notification


notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notification_bp.get("/me")
@auth_required
def get_my_notifications():
    notifications = (
        Notification.query.filter_by(recipientRole=g.user["role"], recipientId=g.user["id"])
        .order_by(Notification.createdAt.desc())
        .all()
    )
    return jsonify([item.to_dict() for item in notifications])


@notification_bp.delete("/me")
@auth_required
def clear_my_notifications():
    return _clear_notifications_for_current_user()


@notification_bp.post("/clear")
@auth_required
def clear_my_notifications_post():
    return _clear_notifications_for_current_user()


def _clear_notifications_for_current_user():
    query = Notification.query.filter_by(
        recipientRole=g.user["role"],
        recipientId=g.user["id"],
    )
    cleared = query.count()
    query.delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"cleared": cleared})


@notification_bp.patch("/<int:notification_id>/read")
@auth_required
def mark_read(notification_id: int):
    notification = Notification.query.filter_by(
        id=notification_id,
        recipientRole=g.user["role"],
        recipientId=g.user["id"],
    ).first()

    if not notification:
        return jsonify({"message": "Notification not found"}), 404

    notification.isRead = True
    db.session.commit()
    return jsonify(notification.to_dict())
