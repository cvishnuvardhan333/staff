from __future__ import annotations

import smtplib
from email.message import EmailMessage

from flask import current_app


SERVICE_HOSTS = {
    "gmail": "smtp.gmail.com",
    "outlook": "smtp-mail.outlook.com",
    "yahoo": "smtp.mail.yahoo.com",
}


def resolve_transport_config() -> dict:
    user = (current_app.config.get("SMTP_USER") or "").strip()
    password = (current_app.config.get("SMTP_PASS") or "").strip()

    if not user or not password:
        raise ValueError("SMTP credentials are not configured")

    service = (current_app.config.get("SMTP_SERVICE") or "").strip().lower()
    host = (current_app.config.get("SMTP_HOST") or "").strip()

    if service:
        host = SERVICE_HOSTS.get(service, host)

    if not host:
        raise ValueError("SMTP host is not configured")

    port = int(current_app.config.get("SMTP_PORT", 587))
    secure = bool(current_app.config.get("SMTP_SECURE")) or port == 465

    return {
        "host": host,
        "port": port,
        "secure": secure,
        "user": user,
        "password": password,
    }


def send_mail(*, to: str, subject: str, text: str) -> None:
    config = resolve_transport_config()

    message = EmailMessage()
    message["From"] = (current_app.config.get("SMTP_FROM") or config["user"]).strip()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)

    if config["secure"]:
        with smtplib.SMTP_SSL(config["host"], config["port"]) as server:
            server.login(config["user"], config["password"])
            server.send_message(message)
        return

    with smtplib.SMTP(config["host"], config["port"]) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config["user"], config["password"])
        server.send_message(message)
