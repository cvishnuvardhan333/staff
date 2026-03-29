from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import relationship

from .extensions import db
from .utils.datetime_helpers import to_iso


class TimestampMixin:
    createdAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Admin(db.Model, TimestampMixin):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="admin")
    resetToken = db.Column(db.String(255), nullable=True)
    resetTokenExpires = db.Column(db.DateTime, nullable=True)

    approvedLeaves = relationship("Leave", back_populates="approver", foreign_keys="Leave.approvedById")

    def to_dict(self, include_password: bool = False) -> dict:
        data = {
            "id": self.id,
            "_id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "resetToken": self.resetToken,
            "resetTokenExpires": to_iso(self.resetTokenExpires),
            "createdAt": to_iso(self.createdAt),
            "updatedAt": to_iso(self.updatedAt),
            # Add autoApproved for admin dashboard tracking (leave info is in leave.to_dict, but can be added here if needed)
        }
        if include_password:
            data["password"] = self.password
        return data


class Staff(db.Model, TimestampMixin):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(255), nullable=False)
    designation = db.Column(db.String(255), nullable=False, default="Faculty")
    phone = db.Column(db.String(50), nullable=True)
    avatarUrl = db.Column(db.String(500), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="staff")
    isActive = db.Column(db.Boolean, nullable=False, default=True)
    resetToken = db.Column(db.String(255), nullable=True)
    resetTokenExpires = db.Column(db.DateTime, nullable=True)
    leaveBalanceTotalAllowed = db.Column(db.Integer, nullable=False, default=20)
    leaveBalanceUsed = db.Column(db.Integer, nullable=False, default=0)

    leaves = relationship("Leave", back_populates="staff", foreign_keys="Leave.staffId")
    timetables = relationship("Timetable", back_populates="staff", foreign_keys="Timetable.staffId")

    def to_dict(self, include_password: bool = False) -> dict:
        data = {
            "id": self.id,
            "_id": self.id,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "designation": self.designation,
            "phone": self.phone,
            "avatarUrl": self.avatarUrl,
            "role": self.role,
            "isActive": self.isActive,
            "resetToken": self.resetToken,
            "resetTokenExpires": to_iso(self.resetTokenExpires),
            "leaveBalanceTotalAllowed": self.leaveBalanceTotalAllowed,
            "leaveBalanceUsed": self.leaveBalanceUsed,
            "createdAt": to_iso(self.createdAt),
            "updatedAt": to_iso(self.updatedAt),
        }
        if include_password:
            data["password"] = self.password
        return data


class Leave(db.Model, TimestampMixin):
    __tablename__ = "leaves"

    id = db.Column(db.Integer, primary_key=True)
    staffId = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    startDate = db.Column(db.DateTime, nullable=False)
    endDate = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    autoApproved = db.Column(db.Boolean, nullable=False, default=False)
    approvedById = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)
    replacementSuggestions = db.Column(db.JSON, nullable=True)

    staff = relationship("Staff", back_populates="leaves", foreign_keys=[staffId])
    approver = relationship("Admin", back_populates="approvedLeaves", foreign_keys=[approvedById])

    def to_dict(self, include_staff: bool = False) -> dict:
        data = {
            "id": self.id,
            "_id": self.id,
            "staffId": self.staffId,
            "type": self.type,
            "startDate": to_iso(self.startDate),
            "endDate": to_iso(self.endDate),
            "reason": self.reason,
            "status": self.status,
            "autoApproved": bool(self.autoApproved),
            "approvedById": self.approvedById,
            "replacementSuggestions": self.replacementSuggestions or [],
            "createdAt": to_iso(self.createdAt),
            "updatedAt": to_iso(self.updatedAt),
        }
        if include_staff:
            data["staff"] = self.staff.to_dict() if self.staff else None
        return data


class Notification(db.Model, TimestampMixin):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipientRole = db.Column(db.String(20), nullable=False)
    recipientId = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="info")
    isRead = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "_id": self.id,
            "recipientRole": self.recipientRole,
            "recipientId": self.recipientId,
            "message": self.message,
            "type": self.type,
            "isRead": self.isRead,
            "createdAt": to_iso(self.createdAt),
            "updatedAt": to_iso(self.updatedAt),
        }


class Timetable(db.Model, TimestampMixin):
    __tablename__ = "timetables"

    id = db.Column(db.Integer, primary_key=True)
    staffId = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    department = db.Column(db.String(255), nullable=False)
    dayOfWeek = db.Column(db.Integer, nullable=False)
    slots = db.Column(db.JSON, nullable=True)

    staff = relationship("Staff", back_populates="timetables", foreign_keys=[staffId])

    __table_args__ = (db.UniqueConstraint("staffId", "dayOfWeek", name="uq_staff_day"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "_id": self.id,
            "staffId": self.staffId,
            "department": self.department,
            "dayOfWeek": self.dayOfWeek,
            "slots": self.slots or [],
            "createdAt": to_iso(self.createdAt),
            "updatedAt": to_iso(self.updatedAt),
        }
