from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ..auth import auth_required, require_role
from ..services.mailer import send_mail
from ..utils.envfile import update_env_file


settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@settings_bp.get("/smtp")
@auth_required
@require_role("admin")
def get_smtp_settings():
    return jsonify(
        {
            "smtpUser": current_app.config.get("SMTP_USER", "") or "",
            "smtpPasswordSet": bool(current_app.config.get("SMTP_PASS")),
        }
    )


@settings_bp.put("/smtp")
@auth_required
@require_role("admin")
def update_smtp_settings():
    payload = request.get_json(silent=True) or {}
    smtp_user = payload.get("smtpUser")
    smtp_password = payload.get("smtpPassword")

    if not isinstance(smtp_user, str) or not smtp_user.strip():
        return jsonify({"message": "SMTP email is required"}), 400

    updates: dict[str, str | None] = {
        "SMTP_USER": smtp_user.strip(),
    }

    if isinstance(smtp_password, str) and smtp_password.strip():
        updates["SMTP_PASS"] = smtp_password.strip()

    update_env_file(ENV_PATH, updates)

    current_app.config["SMTP_USER"] = updates["SMTP_USER"]
    os.environ["SMTP_USER"] = updates["SMTP_USER"] or ""

    if "SMTP_PASS" in updates:
        current_app.config["SMTP_PASS"] = updates["SMTP_PASS"]
        os.environ["SMTP_PASS"] = updates["SMTP_PASS"] or ""

    return jsonify(
        {
            "smtpUser": current_app.config.get("SMTP_USER", "") or "",
            "smtpPasswordSet": bool(current_app.config.get("SMTP_PASS")),
        }
    )


@settings_bp.post("/smtp/test")
@auth_required
@require_role("admin")
def test_smtp_settings():
    payload = request.get_json(silent=True) or {}
    to_email = payload.get("to") if isinstance(payload.get("to"), str) else None

    recipient = (to_email or current_app.config.get("SMTP_USER") or "").strip()
    if not recipient:
        return jsonify({"message": "Recipient email is required for test"}), 400

    try:
        send_mail(
            to=recipient,
            subject="SMTP test",
            text="SMTP settings are working correctly.",
        )
        return jsonify({"message": "Test email sent successfully"})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": str(exc) or "SMTP test failed"}), 400
