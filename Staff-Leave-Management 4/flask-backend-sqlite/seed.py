from __future__ import annotations

from app import create_app
from app.extensions import db
from app.models import Admin, Staff, Timetable
from app.utils.security import generate_password_hash_compat


app = create_app()


with app.app_context():
    db.create_all()

    admin_email = "admin@college.edu"
    admin = Admin.query.filter_by(email=admin_email).first()
    if not admin:
        admin = Admin(
            name="System Admin",
            email=admin_email,
            password=generate_password_hash_compat("Admin@123"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()
    elif admin.password.startswith("scrypt:"):
        admin.password = generate_password_hash_compat("Admin@123")
        db.session.commit()

    staff_count = Staff.query.count()
    if staff_count == 0:
        password_hash = generate_password_hash_compat("Staff@123")

        staff_members = [
            Staff(
                name="Dr. Asha Verma",
                email="asha.verma@college.edu",
                password=password_hash,
                department="Computer Science",
                designation="Assistant Professor",
            ),
            Staff(
                name="Mr. Rohan Mehta",
                email="rohan.mehta@college.edu",
                password=password_hash,
                department="Computer Science",
                designation="Lecturer",
            ),
            Staff(
                name="Ms. Neha Iyer",
                email="neha.iyer@college.edu",
                password=password_hash,
                department="Mathematics",
                designation="Associate Professor",
            ),
            Staff(
                name="Mr. Arjun Nair",
                email="arjun.nair@college.edu",
                password=password_hash,
                department="Mathematics",
                designation="Lecturer",
            ),
        ]

        db.session.add_all(staff_members)
        db.session.commit()

        db.session.add_all(
            [
                Timetable(
                    staffId=staff_members[0].id,
                    department=staff_members[0].department,
                    dayOfWeek=1,
                    slots=[
                        {"label": "Period 1", "startTime": "09:00", "endTime": "10:00", "isFree": False},
                        {"label": "Period 2", "startTime": "10:15", "endTime": "11:15", "isFree": True},
                    ],
                ),
                Timetable(
                    staffId=staff_members[1].id,
                    department=staff_members[1].department,
                    dayOfWeek=1,
                    slots=[
                        {"label": "Period 1", "startTime": "09:00", "endTime": "10:00", "isFree": True},
                        {"label": "Period 2", "startTime": "10:15", "endTime": "11:15", "isFree": True},
                    ],
                ),
                Timetable(
                    staffId=staff_members[2].id,
                    department=staff_members[2].department,
                    dayOfWeek=2,
                    slots=[
                        {"label": "Period 3", "startTime": "11:30", "endTime": "12:30", "isFree": False},
                        {"label": "Period 4", "startTime": "13:30", "endTime": "14:30", "isFree": True},
                    ],
                ),
                Timetable(
                    staffId=staff_members[3].id,
                    department=staff_members[3].department,
                    dayOfWeek=2,
                    slots=[
                        {"label": "Period 3", "startTime": "11:30", "endTime": "12:30", "isFree": True},
                        {"label": "Period 4", "startTime": "13:30", "endTime": "14:30", "isFree": True},
                    ],
                ),
            ]
        )
        db.session.commit()
    else:
        seeded_staff_emails = [
            "asha.verma@college.edu",
            "rohan.mehta@college.edu",
            "neha.iyer@college.edu",
            "arjun.nair@college.edu",
        ]
        seeded_staff = Staff.query.filter(Staff.email.in_(seeded_staff_emails)).all()
        updated = False
        for member in seeded_staff:
            if member.password.startswith("scrypt:"):
                member.password = generate_password_hash_compat("Staff@123")
                updated = True
        if updated:
            db.session.commit()

    print("Seed complete")
