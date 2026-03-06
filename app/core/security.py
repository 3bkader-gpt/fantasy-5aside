import os
import hmac
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SECRET_KEY = os.environ.get("SECRET_KEY") or "super-secret-default-key-for-fantasy-5aside"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if not hashed_password.startswith("$pbkdf2"):
            return hmac.compare_digest(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str, min_length: int = 8) -> None:
    """
    Raise ValueError if password does not meet strength rules.
    Rules: min length, at least one digit, one uppercase, one lowercase.
    """
    if len(password) < min_length:
        raise ValueError(f"كلمة المرور يجب أن تكون {min_length} أحرف على الأقل")
    if not any(c.isdigit() for c in password):
        raise ValueError("كلمة المرور يجب أن تحتوي على رقم واحد على الأقل")
    if not any(c.isupper() for c in password):
        raise ValueError("كلمة المرور يجب أن تحتوي على حرف إنجليزي كبير واحد على الأقل")
    if not any(c.islower() for c in password):
        raise ValueError("كلمة المرور يجب أن تحتوي على حرف إنجليزي صغير واحد على الأقل")

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    to_encode.setdefault("jti", secrets.token_urlsafe(16))
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict | None:
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_token
    except jwt.PyJWTError:
        return None
