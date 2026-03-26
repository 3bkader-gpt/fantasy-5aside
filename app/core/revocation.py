"""JWT revocation: blacklist jti so tokens can be invalidated before expiry."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import models


def revoke_token(db: Session, jti: str, expires_at: datetime) -> None:
    """Add a token's jti to the blacklist until its expiry."""
    row = models.RevokedToken(jti=jti[:64], expires_at=expires_at)
    db.add(row)
    db.commit()


def is_revoked(db: Session, jti: str) -> bool:
    """Return True if jti is in the blacklist and not yet expired."""
    if not jti:
        return True
    now = datetime.now(timezone.utc)
    exists = (
        db.query(models.RevokedToken)
        .filter(models.RevokedToken.jti == jti[:64], models.RevokedToken.expires_at > now)
        .first()
    )
    return exists is not None


def cleanup_expired_tokens(db: Session) -> int:
    """Delete expired revoked tokens and return removed rows count."""
    now = datetime.now(timezone.utc)
    removed = (
        db.query(models.RevokedToken)
        .filter(models.RevokedToken.expires_at <= now)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(removed or 0)
