"""
Migration script to add autoApproved column to leaves table.
Run this script once with your virtual environment activated.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Check if column already exists
    result = db.session.execute(text("PRAGMA table_info(leaves);")).fetchall()
    columns = [row[1] for row in result]
    if "autoApproved" not in columns:
        db.session.execute(text("ALTER TABLE leaves ADD COLUMN autoApproved BOOLEAN NOT NULL DEFAULT 0;"))
        db.session.commit()
        print("autoApproved column added to leaves table.")
    else:
        print("autoApproved column already exists.")
