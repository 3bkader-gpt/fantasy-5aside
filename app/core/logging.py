from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger("uvicorn.error")


def log_event(event: str, **fields: Any) -> None:
    """
    Emit a structured event log line.

    Format is stable key=value pairs to keep logs searchable in Render/Sentry breadcrumbs.
    Never pass secrets (passwords, tokens) in fields.
    """
    safe_event = (event or "").strip()[:80] or "event"
    parts: list[str] = [f"event={safe_event}"]
    for k, v in fields.items():
        if v is None:
            continue
        key = str(k).strip().replace(" ", "_")[:40]
        if not key:
            continue
        val = str(v)
        # Avoid newlines / huge payloads
        val = val.replace("\n", "\\n").replace("\r", "\\r")
        if len(val) > 300:
            val = val[:300] + "…"
        parts.append(f"{key}={val}")
    logger.info(" ".join(parts))

