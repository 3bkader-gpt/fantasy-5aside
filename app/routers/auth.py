import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request, Form, Response, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..core import security
from ..core.csrf import (
    CSRF_COOKIE_NAME,
    get_or_create_csrf_token_from_request,
    set_csrf_cookie,
    verify_csrf_token,
)
from ..core.rate_limit import limiter
from ..core.revocation import is_revoked, revoke_token
from ..dependencies import get_league_repository, get_db, ILeagueRepository, get_current_user
from ..models.user_model import User
if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger("uvicorn.error")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _set_admin_auth_cookies(response: RedirectResponse, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("ENV") == "production",
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=f"Bearer {refresh_token}",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("ENV") == "production",
        max_age=security.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )


def _set_user_auth_cookies(response: RedirectResponse, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="user_access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("ENV") == "production",
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="user_refresh_token",
        value=f"Bearer {refresh_token}",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("ENV") == "production",
        max_age=security.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )


def _revoke_cookie_token(db: "Session", authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        return
    token = authorization.split(" ")[1]
    payload = security.verify_token(token)
    if payload and payload.get("jti") and payload.get("exp"):
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        revoke_token(db, payload["jti"], expires_at)

@router.get("/login")
def login_page(request: Request, msg: str = None):
    token = get_or_create_csrf_token_from_request(request)
    resp = templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"msg": msg, "is_admin": False, "csrf_token": token}
    )
    set_csrf_cookie(resp, token)
    return resp

@router.post("/login")
@limiter.limit("5/minute")
def login_submit(
    request: Request,
    response: Response,
    league_name: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(None),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    league_name = league_name.strip()
    league = league_repo.get_by_name(league_name)
    ip = _client_ip(request)

    if not league or not security.verify_password(password, league.admin_password):
        logger.warning("Login failed ip=%s league_name_len=%d", ip, len(league_name))
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "League name or password incorrect", "is_admin": False}
        )

    logger.info("Login success ip=%s league_slug=%s", ip, league.slug)
    # Valid credentials, create token
    token = security.create_access_token(
        data={"sub": league.slug, "league_id": league.id, "scope": "admin"}
    )
    refresh_token = security.create_refresh_token(
        data={"sub": league.slug, "league_id": league.id, "scope": "admin"}
    )
    
    # Redirect to admin dashboard
    redirect = RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)
    _set_admin_auth_cookies(redirect, token, refresh_token)
    return redirect


@router.post("/user/login")
@limiter.limit("10/minute")
def user_login_submit(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(None),
    db: "Session" = Depends(get_db),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    email_clean = email.strip().lower()
    from ..models.user_model import User  # local import to avoid circulars in some tools

    user: User | None = (
        db.query(User)
        .filter(User.email == email_clean)
        .first()
    )
    if not user or not security.verify_password(password, user.hashed_password):
        csrf_bad = get_or_create_csrf_token_from_request(request)
        resp_bad = templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Email or password incorrect",
                "is_admin": False,
                "csrf_token": csrf_bad,
            },
        )
        set_csrf_cookie(resp_bad, csrf_bad)
        return resp_bad

    if not user.is_verified:
        csrf = get_or_create_csrf_token_from_request(request)
        resp = templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "يجب تفعيل البريد الإلكتروني قبل تسجيل الدخول. راجع رسالة التفعيل أو أعد طلب الإرسال من الرابط أدناه.",
                "needs_verification": True,
                "pending_email": user.email,
                "is_admin": False,
                "csrf_token": csrf,
            },
        )
        set_csrf_cookie(resp, csrf)
        return resp

    token = security.create_access_token(data={"sub": str(user.id), "scope": "user"})
    refresh_token = security.create_refresh_token(data={"sub": str(user.id), "scope": "user"})
    redirect = RedirectResponse(url="/dashboard", status_code=303)
    _set_user_auth_cookies(redirect, token, refresh_token)
    return redirect

@router.get("/logout")
def logout(request: Request, db: "Session" = Depends(get_db)):
    _revoke_cookie_token(db, request.cookies.get("access_token"))
    _revoke_cookie_token(db, request.cookies.get("user_access_token"))
    _revoke_cookie_token(db, request.cookies.get("refresh_token"))
    _revoke_cookie_token(db, request.cookies.get("user_refresh_token"))
    redirect = RedirectResponse(url="/?msg=logged_out", status_code=303)
    redirect.delete_cookie("access_token")
    redirect.delete_cookie("user_access_token")
    redirect.delete_cookie("refresh_token")
    redirect.delete_cookie("user_refresh_token")
    return redirect


@router.post("/refresh")
def refresh_session(request: Request, db: "Session" = Depends(get_db)):
    admin_refresh = request.cookies.get("refresh_token")
    user_refresh = request.cookies.get("user_refresh_token")

    if admin_refresh and admin_refresh.startswith("Bearer "):
        payload = security.verify_token(admin_refresh.split(" ")[1])
        if not payload or payload.get("token_type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        if payload.get("scope") != "admin":
            raise HTTPException(status_code=401, detail="Invalid refresh scope")
        if payload.get("jti") and is_revoked(db, payload["jti"]):
            raise HTTPException(status_code=401, detail="Refresh token revoked")

        _revoke_cookie_token(db, admin_refresh)
        access = security.create_access_token(
            {
                "sub": payload.get("sub"),
                "league_id": payload.get("league_id"),
                "scope": "admin",
            }
        )
        refresh = security.create_refresh_token(
            {
                "sub": payload.get("sub"),
                "league_id": payload.get("league_id"),
                "scope": "admin",
            }
        )
        resp = RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)
        _set_admin_auth_cookies(resp, access, refresh)
        return resp

    if user_refresh and user_refresh.startswith("Bearer "):
        payload = security.verify_token(user_refresh.split(" ")[1])
        if not payload or payload.get("token_type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        if payload.get("scope") != "user":
            raise HTTPException(status_code=401, detail="Invalid refresh scope")
        if payload.get("jti") and is_revoked(db, payload["jti"]):
            raise HTTPException(status_code=401, detail="Refresh token revoked")

        _revoke_cookie_token(db, user_refresh)
        access = security.create_access_token({"sub": payload.get("sub"), "scope": "user"})
        refresh = security.create_refresh_token({"sub": payload.get("sub"), "scope": "user"})
        resp = RedirectResponse(url="/dashboard", status_code=303)
        _set_user_auth_cookies(resp, access, refresh)
        return resp

    raise HTTPException(status_code=401, detail="No refresh token provided")
