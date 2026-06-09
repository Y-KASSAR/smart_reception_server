"""
Time Utilities
==============
Timestamp formatting and duration helpers.
"""
from datetime import datetime, timezone


def utcnow_str(fmt: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """Return current UTC time as a formatted string."""
    return datetime.now(timezone.utc).strftime(fmt)


def seconds_to_human(seconds: float) -> str:
    """
    Convert seconds to a human-readable duration string.

    Examples:
        45   -> "45s"
        90   -> "1m 30s"
        3661 -> "1h 1m 1s"
    """
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def timestamp_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()