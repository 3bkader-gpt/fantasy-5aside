import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 2
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 14

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def is_password_hash(value: str | None) -> bool:
    """Return True when value looks like a passlib-supported password hash."""
    if not value:
        return False
    return bool(pwd_context.identify(value))


def migrate_legacy_plaintext_admin_passwords(db_session: Any) -> int:
    """Hash legacy plaintext league admin passwords in-place.

    This helper is intentionally idempotent and can be called at startup.
    """
    from app.models.models import League

    updated = 0
    leagues = db_session.query(League).all()
    for league in leagues:
        current = (league.admin_password or "").strip()
        if not current or is_password_hash(current):
            continue
        league.admin_password = get_password_hash(current)
        db_session.add(league)
        updated += 1

    if updated:
        db_session.commit()
    return updated


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str, min_length: int = 12) -> None:
    """
    Raise ValueError if password does not meet strength rules.
    Rules: min length, at least one digit, one uppercase, one lowercase, one special character.
    """
    if len(password) < min_length:
        raise ValueError(f"كلمة المرور يجب أن تكون {min_length} أحرف على الأقل")
    if not any(c.isdigit() for c in password):
        raise ValueError("كلمة المرور يجب أن تحتوي على رقم واحد على الأقل")
    if not any(c.isupper() for c in password):
        raise ValueError("كلمة المرور يجب أن تحتوي على حرف إنجليزي كبير واحد على الأقل")
    if not any(c.islower() for c in password):
        raise ValueError("كلمة المرور يجب أن تحتوي على حرف إنجليزي صغير واحد على الأقل")
    if not any(not c.isalnum() for c in password):
        raise ValueError("كلمة المرور يجب أن تحتوي على رمز خاص واحد على الأقل")

def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    to_encode.setdefault("jti", secrets.token_urlsafe(16))
    to_encode["token_type"] = "access"
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    to_encode.setdefault("jti", secrets.token_urlsafe(16))
    to_encode["token_type"] = "refresh"
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict | None:
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_token
    except jwt.PyJWTError:
        return None
