from __future__ import annotations

import os
from datetime import datetime

from n3rv.config import RuntimeSettings


def get_hub_url(settings: RuntimeSettings | None = None) -> str:
    default_url = settings.a2a_base_url if settings else "http://127.0.0.1:19820"
    return os.getenv("N3RV_HUB_URL", default_url)


def format_age(timestamp: str, suffix: str = "") -> str:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo)
        delta = now - dt
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s{suffix}"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}m{suffix}"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)}h{suffix}"
        else:
            return f"{int(delta.total_seconds() / 86400)}d{suffix}"
    except Exception:
        return "unknown"
