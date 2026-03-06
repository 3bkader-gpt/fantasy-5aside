"""Audit logging for admin actions (who did what, when)."""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import models


def log_audit(
    db: Session,
    league_id: int,
    action: str,
    actor: str | None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an audit record. Do not log passwords or tokens in details."""
    details_str = json.dumps(details, ensure_ascii=False) if details else None
    entry = models.AuditLog(
        league_id=league_id,
        action=action[:64],
        actor=(actor or "anonymous")[:128],
        details=details_str,
    )
    db.add(entry)
    db.commit()
