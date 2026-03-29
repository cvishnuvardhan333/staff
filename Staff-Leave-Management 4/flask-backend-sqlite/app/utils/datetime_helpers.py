from __future__ import annotations

from datetime import date, datetime, timezone


def parse_datetime(value: str | date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if len(raw) == 10 and raw.count("-") == 2:
            dt = datetime.strptime(raw, "%Y-%m-%d")
        else:
            normalized = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
    else:
        raise ValueError("Unsupported datetime value")

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def to_date_string(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")
