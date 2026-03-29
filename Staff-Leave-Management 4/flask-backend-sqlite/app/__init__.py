from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from .config import Config
from .extensions import db
from .routes.auth_routes import auth_bp
from .routes.leave_routes import leave_bp
from .routes.notification_routes import notification_bp
from .routes.settings_routes import settings_bp
from .routes.staff_routes import staff_bp
from .routes.timetable_routes import timetable_bp


def create_app() -> Flask:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    frontend_dist = Path(os.getenv("FRONTEND_DIST", Config.FRONTEND_DIST)).resolve()

    app = Flask(
        __name__,
        static_folder=str(frontend_dist) if frontend_dist.exists() else None,
        static_url_path="",
    )
    app.config.from_object(Config)
    app.config["FRONTEND_DIST"] = str(frontend_dist)

    CORS(app)
    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(timetable_bp)
    app.register_blueprint(settings_bp)

    @app.get("/")
    def index():
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return send_from_directory(frontend_dist, "index.html")
        return jsonify({"status": "Smart Staff Leave Management System API"})

    @app.get("/api")
    def api_index():
        return jsonify({"status": "Smart Staff Leave Management System API"})

    @app.route("/<path:path>")
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            return jsonify({"message": "Not found"}), 404

        target = frontend_dist / path
        if target.exists() and target.is_file():
            return send_from_directory(frontend_dist, path)

        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return send_from_directory(frontend_dist, "index.html")

        return jsonify({"message": "Frontend build not found in FRONTEND_DIST."}), 404

    @app.errorhandler(404)
    def not_found(_err):
        if request.path == "/api" or request.path.startswith("/api/"):
            return jsonify({"message": "Not found"}), 404

        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return send_from_directory(frontend_dist, "index.html")
        return jsonify({"message": "Not found"}), 404

    with app.app_context():
        db.create_all()

    return app
