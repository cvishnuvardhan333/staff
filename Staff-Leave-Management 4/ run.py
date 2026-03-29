#!/usr/bin/env python3

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
FLASK_PROJECT_DIR = ROOT_DIR / "flask-backend-sqlite"

sys.path.insert(0, str(FLASK_PROJECT_DIR))

from app import create_app  # noqa: E402


app = create_app()


def _port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _find_open_port(host: str, preferred_port: int) -> int:
    if _port_is_available(host, preferred_port):
        return preferred_port

    for port in range(preferred_port + 1, 65536):
        if _port_is_available(host, port):
            return port

    raise RuntimeError("No available TCP port found.")


def _discover_lan_ipv4_addresses() -> list[str]:
    addresses = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        return []
    return sorted(addresses)


def _startup_urls(host: str, port: int) -> list[str]:
    if host in {"0.0.0.0", "::"}:
        urls = [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]
        urls.extend(f"http://{ip}:{port}" for ip in _discover_lan_ipv4_addresses())
    else:
        urls = [f"http://{host}:{port}"]

    ordered_unique = []
    for url in urls:
        if url not in ordered_unique:
            ordered_unique.append(url)
    return ordered_unique


if __name__ == "__main__":
    host = str(app.config.get("HOST", "0.0.0.0"))
    requested_port = int(app.config.get("PORT", 5001))
    port = _find_open_port(host, requested_port)
    debug = bool(app.config.get("DEBUG", False))

    is_reloader_process = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not is_reloader_process:
        if port != requested_port:
            print(f"Port {requested_port} is in use. Starting on port {port} instead.")
        print("Local links:")
        for url in _startup_urls(host, port):
            print(f"  {url}")

    app.run(host=host, port=port, debug=debug)
