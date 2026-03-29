from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _bool_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("JWT_SECRET", "replace-this-with-a-long-random-jwt-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'staff_leave.sqlite3'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PORT = int(os.getenv("PORT", "5001"))
    DEBUG = _bool_env(os.getenv("FLASK_DEBUG"), default=False)

    FRONTEND_DIST = os.getenv("FRONTEND_DIST", str(BASE_DIR / "web"))
    APP_URL = os.getenv("APP_URL", "http://localhost:5001")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5001")

    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    SMTP_SERVICE = os.getenv("SMTP_SERVICE", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_SECURE = _bool_env(os.getenv("SMTP_SECURE"), default=False)
    SMTP_FROM = os.getenv("SMTP_FROM", "")
