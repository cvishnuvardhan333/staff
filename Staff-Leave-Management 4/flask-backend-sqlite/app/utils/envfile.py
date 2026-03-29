from __future__ import annotations

from pathlib import Path


def format_env_value(value: str | None) -> str:
    text = "" if value is None else str(value)
    if text == "":
        return ""
    if any(ch.isspace() for ch in text) or "#" in text:
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


def upsert_env_value(lines: list[str], key: str, value: str | None) -> list[str]:
    found = False
    updated: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            updated.append(line)
            continue

        current_key = line.split("=", 1)[0].strip()
        if current_key != key:
            updated.append(line)
            continue

        found = True
        updated.append(f"{key}={format_env_value(value)}")

    if not found:
        updated.append(f"{key}={format_env_value(value)}")

    return updated


def update_env_file(env_path: Path, updates: dict[str, str | None]) -> None:
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = existing.splitlines()

    for key, value in updates.items():
        lines = upsert_env_value(lines, key, value)

    payload = "\n".join(lines).strip()
    env_path.write_text((payload + "\n") if payload else "", encoding="utf-8")
