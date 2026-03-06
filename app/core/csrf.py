"""CSRF protection: double-submit cookie pattern."""
import os
import hmac
import secrets
from typing import Optional

from fastapi import Request, HTTPException
from starlette.responses import Response

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_MAX_AGE = 3600  # 1 hour


def generate_csrf_token() -> str:
    """Generate a random token for CSRF double-submit."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set the CSRF token in a cookie (readable by JS for double-submit)."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=CSRF_MAX_AGE,
        samesite="lax",
        secure=os.environ.get("ENV") == "production",
        httponly=False,  # so JS can read for X-CSRF-Token header
    )


def verify_csrf_token(cookie_token: Optional[str], submitted_token: Optional[str]) -> bool:
    """Timing-safe comparison of cookie token and submitted token."""
    if not cookie_token or not submitted_token:
        return False
    return hmac.compare_digest(cookie_token.strip(), submitted_token.strip())


async def verify_csrf(request: Request) -> None:
    """
    Dependency: for POST/PUT/PATCH/DELETE, require valid CSRF token.
    Reads token from X-CSRF-Token header (for JSON/fetch) or raises if missing.
    Form endpoints should read csrf_token from Form and call verify_csrf_token manually.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not verify_csrf_token(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
